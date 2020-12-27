"""
Contains methods to query user info and stats from the Github API.

Note that Github hosts two APIs, a REST API (also known as v3) and a GraphQL API (v4),
which are both used here. Expensive API calls are cached via streamlit's `st.cache`.
"""

import os
import time
from datetime import datetime
import copy
from typing import Dict, Tuple, List

from ghapi.core import GhApi
from ghapi.page import pages
from dotenv import load_dotenv
import requests
from fastcore.net import HTTP404NotFoundError
import streamlit as st

import utils


# Set up the Github REST API client.
# Note that ghapi contains a bug in the `paged` method as of December 2020, therefore
# it's safer to install my fork (see README.md for instructions).
load_dotenv()
api = GhApi(
    token=os.getenv("GH_TOKEN"),
    limit_cb=lambda rem, quota: print(f"Quota remaining: {rem} of {quota}"),
)


def rate_limit_info() -> Dict:
    """Return information about reamining API calls (on REST API and GraphQL API)."""
    limits = api.rate_limit.get()
    d = {
        "core_remaining": limits.resources.core.remaining,
        "core_reset": utils.format_timedelta(
            datetime.fromtimestamp(limits.resources.core.reset) - datetime.now()
        ),
        "graphql_remaining": limits.resources.graphql.remaining,
        "graphql_reset": utils.format_timedelta(
            datetime.fromtimestamp(limits.resources.graphql.reset) - datetime.now()
        ),
    }
    return d


class UserNotFoundError(Exception):
    pass


@st.cache(hash_funcs={"ghapi.core._GhVerb": lambda _: None}, show_spinner=False)
def _query_user(username: str, year: int) -> Tuple:
    """Retrieves user infos + own repos + external repos from the Github API."""

    print("-" * 80)
    print("Querying API for user:", username)
    print()
    start_time = time.time()

    # 1) Query REST API to find out if the user is an organization. This has to be done
    #    first because the following queries are different for users and orgs.
    try:
        user = api.users.get_by_username(username)
    except HTTP404NotFoundError:
        raise UserNotFoundError(
            f"Received 404 error when searching for user: {username}"
        )
    is_org = user.type == "Organization"
    num_repos = user.public_repos

    # 2) Query REST API to get all repos that the user owns and count their new stars.
    # TODO: Maybe do this with the GraphQL API. Bit more complicated to handle
    #   pagination though + it's a lot of new code for 0.5 s performance increase.
    own_repo_stars = {}
    endpoint = api.repos.list_for_org if is_org else api.repos.list_for_user
    num_pages = 1 + int(num_repos / 100)
    for repo in pages(endpoint, num_pages, username).concat():

        print(
            f"{repo.full_name[:40]:40} (created: {repo.created_at}, stars: {repo.stargazers_count})",
        )

        # Count new stars (several options to minimize time & amount of API calls).
        if repo.stargazers_count == 0:
            new_stars = 0
            print("No stars at all")
        elif int(repo.created_at[:4]) == year:
            new_stars = repo.stargazers_count
            print("Created this year, count all stars:", new_stars)
        else:
            new_stars = None
            print("Needs intense analysis, do later")
        own_repo_stars[repo.full_name] = new_stars
        print()

    # 3) Query GraphQL API to get contribution counts + external repos.
    if is_org:
        # TODO: Maybe count commits (+ maybe issues/prs) for this year across all repos.
        contributions = 0
        repos_contributed_to = 0
        external_repo_stars = {}
    else:
        url = "https://api.github.com/graphql"
        headers = {"Authorization": f"bearer {os.getenv('GH_TOKEN')}"}
        query = f"""query {{
            user(login: "{username}") {{
                contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{year}-12-31T23:59:59Z") {{
                    contributionCalendar {{
                        totalContributions
                    }}
                    totalRepositoriesWithContributedCommits
                    commitContributionsByRepository(maxRepositories: 100) {{
                        repository {{
                            nameWithOwner
                            createdAt
                            stargazerCount
                        }}
                        contributions {{
                            totalCount
                        }}
                    }}
                }}
            }}
        }}"""

        # TODO: Filter bad response, especially user not known.
        response = requests.post(url, headers=headers, json={"query": query})
        contrib_collection = response.json()["data"]["user"]["contributionsCollection"]
        contributions = contrib_collection["contributionCalendar"]["totalContributions"]
        # Repos are already sorted from GraphQL by number of contributions.
        # TODO: This only returns 100 (?) repos at most. Does it make sense to get more via
        #   pagination here? -> Probably nobody contributes to more than 100 repos (or wants
        #   to show all of these results).
        repos_contributed_to = contrib_collection[
            "totalRepositoriesWithContributedCommits"
        ]
        external_repos = [
            item["repository"]
            for item in contrib_collection["commitContributionsByRepository"]
            if item["repository"]["nameWithOwner"].split("/")[0] != username
        ]

        # TODO: Maybe pass number of commits outside as well and show it in checkboxes.

        # Parse external repos but do not do binary search here (it's too expensive
        # and will be done later when required).
        external_repo_stars = {}
        for repo in external_repos:
            print(
                f"{repo['nameWithOwner'][:40]:40} (created: {repo['createdAt']}, stars: {repo['stargazerCount']})",
            )

            # Count new stars (several options to minimize time & amount of API calls).
            if repo["stargazerCount"] == 0:
                new_stars = 0
                print("No stars at all")
            elif int(repo["createdAt"][:4]) == year:
                new_stars = repo["stargazerCount"]
                print("Created this year, count all stars:", new_stars)
            else:
                new_stars = None
                print("Needs intense analysis, do later")
            external_repo_stars[repo["nameWithOwner"]] = new_stars
            print()

    print(f"Took {time.time() - start_time} s")
    print("-" * 80)

    return (
        is_org,
        contributions,
        repos_contributed_to,
        own_repo_stars,
        external_repo_stars,
    )


@st.cache(hash_funcs={"ghapi.core._GhVerb": lambda _: None}, show_spinner=False)
def _query_repo(full_name: str, year: int) -> int:
    """Returns number of new stars in a year through binary search on the Github API."""

    # Calculate number of pages. Each page has 100 items.
    # num_pages = 1 + int(stargazers_count / 100)  # round up

    def get_stargazers(page: int):
        """Retrieves a page of stargazers from the Github API."""
        # TODO: This throws an error when parsing very big and old repos, because very
        # old records are not returned. E.g. sindresorhus/awesome has 150k stars,
        # but it stops after around 400 pages. fastcore.basics.HTTP422UnprocessableEntityError
        return api.activity.list_stargazers_for_repo(
            *full_name.split("/"),
            headers={"Accept": "application/vnd.github.v3.star+json"},
            per_page=100,
            page=page,
        )

    def count_new(stargazers) -> int:
        """Returns number of stargazers who starred in `year`."""
        new_stars = 0
        for stargazer in stargazers:
            if int(stargazer.starred_at[:4]) == year:
                new_stars += 1
        return new_stars

    # Query first page of stargazers (required to retrieve total number of pages).
    # Also, most repos only have one page anyway (i.e. <100 stars).
    stargazers = get_stargazers(1)
    new_stars = count_new(stargazers)
    num_pages = max(1, api.last_page())  # ghapi returns 0 here if there's only 1 page
    print("Total pages:", num_pages)

    if num_pages == 1:  # only one page
        print("Total new stars:", new_stars)
        return new_stars
    elif new_stars > 0 and new_stars < len(stargazers):  # break is on first page
        print("Found year break on first page")

        # Add all stars on the last page.
        new_stars += len(get_stargazers(num_pages))

        # Add 100 stars for each page in between.
        if num_pages > 2:
            new_stars += (num_pages - 2) * 100

        print("Total new stars:", new_stars)
        return new_stars
    else:
        # If there's more than 1 page: Use binary search to find the page that contains
        # the break from 2019 to 2020.
        # Start on 2nd page b/c we already searched the 1st one.
        from_page = 2
        to_page = num_pages

        while from_page <= to_page:
            page = (from_page + to_page) // 2
            print(f"Searching from page {from_page} to {to_page}, looking at {page}")

            # Get year of first and last stargazer on the page.
            stargazers = get_stargazers(page)
            top_year = int(stargazers[0].starred_at[:4])
            bottom_year = int(stargazers[-1].starred_at[:4])
            # print(top_year, bottom_year)

            # TODO: Check if everything works properly for 2021.
            if from_page == to_page or (top_year < year and bottom_year >= year):
                # Either `page` is the one with the year break, or we reached the first
                # or last page and the year break is not contained in any page.
                print("Page:", page, "-> found it!")
                break
            elif bottom_year < year and top_year < year:  # before 2020
                from_page = min(num_pages, page + 1)
                print("Page:", page, "-> before 2020, setting from_page to:", from_page)
            elif bottom_year >= year and top_year >= year:  # equal to or after 2020
                to_page = max(1, page - 1)
                print("Page:", page, "-> before 2020, setting to_page to:", to_page)
            else:
                raise RuntimeError()
            # print()

        # Count new stars on `page`.
        new_stars = count_new(stargazers)

        # Add all stars on the last page.
        if page < num_pages:
            new_stars += len(get_stargazers(num_pages))

        # Add 100 stars for each page in between.
        if page < num_pages - 1:
            new_stars += (num_pages - 1 - page) * 100

        print("Total new stars:", new_stars)
        return new_stars


class StatsMaker:
    def __init__(self, username: str, year: int):
        """
        Initializes an object, which queries and stores the Github stats for a user.

        This calls the cached functions above to query the API. Note that these
        functions cannot be included directly in this class because streamlit's
        caching mechanism wouldn't work properly then.
        """
        self.username = username
        self.year = year

        # Query some basic information for the user. Shouldn't take more than 1-3 s.
        (
            self.is_org,
            self.contributions,
            self.repos_contributed_to,
            own_repo_stars,
            external_repo_stars,
        ) = _query_user(username, year)

        # Copy the returned dicts because streamlit doesn't allow mutating return
        # values of cached functions.
        self.own_repo_stars = copy.deepcopy(own_repo_stars)
        self.external_repo_stars = copy.deepcopy(external_repo_stars)

        # Make a list with the names of external repos.
        # TODO: Check again that this is ordered by the number of contributions.
        self.external_repos = list(self.external_repo_stars.keys())

        # TODO:
        # - contributions -> for org: contributions to all its repos
        # - num of repos contributed to -> for org: number of repos that the org owns that were contributed to

    def stream(self, include_external: List = None):
        """
        Generator that calculates the stats and yields intermediate results.

        Args:
            include_external (list, optional): Names of external repos to include in
                the count. A list of all external repos is contained in
                `self. external_repos`. Defaults to `None`, in which case only the
                user's own repos are counted.

        Yields:
            (dict, float, str): Intermediate stats as a dict, the current progress
                (0-1), and a progress message
        """

        print("-" * 80)
        print("Streaming stats for user:", self.username)
        print()
        start_time = time.time()

        if include_external is None:
            include_external = []

        # Construct list of all repos that need to be queried (i.e. all the ones
        # where we didn't evaluate the number of new stars yet).
        repos_to_query = [
            repo for repo, new_stars in self.own_repo_stars.items() if new_stars is None
        ]
        for repo in include_external:
            if self.external_repo_stars[repo] is None:
                repos_to_query.append(repo)

        def progress_msg(repo_idx):
            try:
                return f"Parsing repo: {repos_to_query[repo_idx]}"
            except IndexError:
                return "Finished"

        # Yield once in the beginning, to show already existing stats.
        progress = 0.2 if repos_to_query else 1.0
        yield self._compute_stats(include_external), progress, progress_msg(0)

        # Perform the queries, store results and yield intermediate performance.
        for i, repo in enumerate(repos_to_query):
            # TODO: Maybe print in _query_repo instead.
            print(repo)
            new_stars = _query_repo(repo, self.year)
            print()

            if repo in self.own_repo_stars:
                self.own_repo_stars[repo] = new_stars
            elif repo in self.external_repo_stars:
                self.external_repo_stars[repo] = new_stars
            else:
                raise RuntimeError()

            progress = min(1.0, 0.2 + 0.8 * (i + 1) / len(repos_to_query))
            yield self._compute_stats(include_external), progress, progress_msg(i + 1)

        # Yield stats one more time, in case no repo was queried changed above.
        # TODO: I think this is not required any more but check again.
        # yield self._compute_stats(include_external), 1.0, "Finished"

        print(f"Took {time.time() - start_time} s")
        print("-" * 80)

    def _compute_stats(self, include_external: List):
        """Computes intermediate statistics."""
        # Compile all repos that should be included in the current count (i.e. are own
        # repo or included external repo and have stars != None).
        all_repo_stars = {
            **self.own_repo_stars,
            **{repo: self.external_repo_stars[repo] for repo in include_external},
        }
        all_repo_stars = {k: v for k, v in all_repo_stars.items() if v is not None}

        # Compute total number of new stars.
        new_stars = sum(all_repo_stars.values())

        # Find hottest repo (= the one with the most new stars).
        if new_stars > 0:
            hottest = max(all_repo_stars.items(), key=lambda item: item[1])
            hottest_repo, hottest_new_stars = hottest
        else:
            # TODO: Select repo with most stars overall instead, or just the first one.
            hottest_repo, hottest_new_stars = None, None

        stats = {
            "username": self.username,
            # "avatar_url": avatar_url,
            "is_org": self.is_org,
            "contributions": self.contributions,
            "repos_contributed_to": self.repos_contributed_to,
            # "new_repos": new_repos,
            "new_stars": new_stars,
            # "hottest_name": hottest_name,
            "hottest_repo": hottest_repo,
            "hottest_new_stars": hottest_new_stars,
            # "external_repos": external_repos,
        }
        return stats


# TODO: Old code, delete once I've ported everything to the code above.
# def _get_contributions(username, year, verbose=False):
#     """
#     Returns number of total contributions from Github's GraphQL API.

#     Contributions = Commits + issues + PRs (public and private). This is the same value
#     that's shown on the user's profile page on the commit calendar.

#     Endpoint: https://docs.github.com/en/free-pro-team@latest/graphql/reference/objects#contributioncalendar
#     Some examples at: https://stackoverflow.com/questions/18262288/finding-total-contributions-of-a-user-from-github-api
#     GraphQL API Explorer: https://docs.github.com/en/free-pro-team@latest/graphql/overview/explorer
#     """
#     print("-" * 80)
#     print("Reading GraphQL API for user:", username)
#     start_time = time.time()

#     # Set up query params.
#     url = "https://api.github.com/graphql"
#     headers = {"Authorization": f"bearer {os.getenv('GH_TOKEN')}"}
#     query = f"""query {{
#         user(login: "{username}") {{
#             contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{year}-12-31T23:59:59Z") {{
#                 contributionCalendar {{
#                     totalContributions
#                 }}
#                 commitContributionsByRepository {{
#                     repository {{
#                         owner {{
#                             login
#                         }}
#                         name
#                         stargazerCount
#                     }}
#                     contributions {{
#                         totalCount
#                     }}
#                 }}
#             }}
#         }}
#     }}"""

#     # Make POST request to GraphQL API. Takes 0.3-0.6 s.
#     response = requests.post(url, headers=headers, json={"query": query})
#     # TODO: Filter bad response.
#     collection = response.json()["data"]["user"]["contributionsCollection"]
#     contributions = collection["contributionCalendar"]["totalContributions"]
#     # Repos are already sorted from GraphQL by number of contributions.
#     external_repos = [
#         item["repository"]["owner"]["login"] + "/" + item["repository"]["name"]
#         for item in collection["commitContributionsByRepository"]
#         if item["repository"]["owner"]["login"] != username
#     ]

#     print(external_repos)

#     if verbose:
#         print(f"Contributions: {contributions}")

#     print("Read contributions:", time.time() - start_time)
#     return contributions, external_repos


# def stream_stats(username, year, count_external_repos=None, verbose=False):
#     """
#     Generator that reads user stats from Github and yields them while reading.

#     Note that this function calls Github's REST API (v3) as well as its GraphQL API
#     (v4). The REST API has a rate limit of 5000 calls per hour, the GraphQL has a
#     similar rate limit (which is not straightforward to calculate though).
#     """

#     # Get some basic info about the user (and check that it exists!).
#     avatar_url, is_org = _get_user_info(username)

#     # Fetch number of contributions through GraphQL API.
#     if is_org:
#         # TODO: Maybe count commits (+ maybe issues/prs) for this year across all repos.
#         contributions = 0
#         external_repos = []
#     else:
#         contributions, external_repos = _get_contributions(
#             username, year, verbose=verbose
#         )

#     new_repos = 0
#     new_stars_per_repo = defaultdict(lambda: 0)

#     def summary_stats():
#         """Calculate summary stats out of the values retrieved so far."""
#         # Takes e-5 s.
#         new_stars = sum(new_stars_per_repo.values())
#         if new_stars > 0:
#             hottest = max(new_stars_per_repo.items(), key=lambda item: item[1])
#             # hottest_name, hottest_new_stars = hottest
#             # hottest_full_name = username + "/" + hottest_name
#             hottest_full_name, hottest_new_stars = hottest
#         else:
#             # TODO: Select repo with most stars overall instead, or just the first one.
#             hottest_full_name, hottest_new_stars = None, None

#         stats = {
#             "username": username,
#             "avatar_url": avatar_url,
#             "is_org": is_org,
#             "contributions": contributions,
#             "new_repos": new_repos,
#             "new_stars": new_stars,
#             # "hottest_name": hottest_name,
#             "hottest_full_name": hottest_full_name,
#             "hottest_new_stars": hottest_new_stars,
#             "external_repos": external_repos,
#         }
#         return stats

#     print("-" * 80)
#     print("Reading API for user:", username)
#     start_time = time.time()
#     repos_to_inspect = []

#     # Make one quick loop through all repos and crawl basic stats where possible.
#     # Repos that need closer inspection (i.e. where we need to look at all stargazers
#     # in detail) are added to `repos_to_inspect`.
#     # Use `paged` instead of `pages` here because most users will have <100 repos anyway
#     # and getting the number of pages would require an additional API call.
#     print("Quick inspection:")
#     endpoint = api.repos.list_for_org if is_org else api.repos.list_for_user
#     for repos in paged(endpoint, username, per_page=100,):
#         print("Got one page of repos:", time.time() - start_time)
#         for repo in repos:
#             print(
#                 f"{repo.full_name[:30]:30}: created: {repo.created_at}, stars: {repo.stargazers_count}",
#                 end="",
#             )

#             # Check if repo is new. Takes e-7 s.
#             if int(repo.created_at[:4]) == year:
#                 new_repos += 1

#             # Count new stars (several options to minimize time & amount of API calls).
#             if repo.stargazers_count == 0:
#                 # Option 1: 0 stars, so also 0 new stars. Takes e-6 s.
#                 new_stars_per_repo[repo.full_name] = 0
#             elif int(repo.created_at[:4]) == year:
#                 # Option 2: Created this year, therefore take all stars. Takes e-5 s.
#                 new_stars_per_repo[repo.full_name] = repo.stargazers_count
#             else:
#                 # Option 3: Save for later inspection (see below; looks at all
#                 # stargazers in detail).
#                 repos_to_inspect.append((repo.full_name, repo.stargazers_count))
#                 print("-> closer inspection", end="")
#             print()

#     # TODO: Refactor all of this.
#     print("Quick inspection of external repos:")
#     if count_external_repos is not None:
#         for full_name in count_external_repos:

#             # TODO: Get these numbers already in GraphQL query above and store them.
#             repo = api.repos.get(*full_name.split("/"))
#             print(
#                 f"{repo.full_name[:30]:30}: created: {repo.created_at}, stars: {repo.stargazers_count}",
#                 end="",
#             )

#             # Check if repo is new. Takes e-7 s.
#             if int(repo.created_at[:4]) == year:
#                 new_repos += 1

#             # Count new stars (several options to minimize time & amount of API calls).
#             if repo.stargazers_count == 0:
#                 # Option 1: 0 stars, so also 0 new stars. Takes e-6 s.
#                 new_stars_per_repo[repo.full_name] = 0
#             elif int(repo.created_at[:4]) == year:
#                 # Option 2: Created this year, therefore take all stars. Takes e-5 s.
#                 new_stars_per_repo[repo.full_name] = repo.stargazers_count
#             else:
#                 # Option 3: Save for later inspection (see below; looks at all
#                 # stargazers in detail).
#                 repos_to_inspect.append((repo.full_name, repo.stargazers_count))
#                 print("-> closer inspection", end="")
#             print()

#     # Sort repos_to_inspect so we look at the ones with most stars first.
#     # TODO: If people have very large repos, it might be better to do a medium sized
#     # one first, so they see some progress.
#     repos_to_inspect = sorted(repos_to_inspect, key=lambda item: item[1], reverse=True)

#     def progress_msg(next_repo_idx):
#         """Generate progress message for the next repo in closer inspection."""
#         try:
#             msg = f"Parsing repo: {repos_to_inspect[next_repo_idx][0]}"
#             if repos_to_inspect[next_repo_idx][1] > 1000:
#                 msg += " (wow, so many ⭐, this takes a bit!)"
#         except IndexError:  # last repo doesn't have next one
#             msg = ""
#         return msg

#     # Yield intermediate results.
#     yield summary_stats(), 0.2, progress_msg(0)

# print()
# print("Closer inspection:")
# for i, (full_name, stargazers_count) in enumerate(repos_to_inspect):
#     # TODO: Maybe set a maximum number of API calls/pages here. Then again,
#     # even for the repo with the most stars on Github (300k), the binary search
#     # shouldn't take more than 19 steps.
#     print(
#         f"{full_name[:30]:30}: stars: ({stargazers_count})", end="",
#     )
#     stars_start_time = time.time()

#     # COMBINED WITH 1000 STARS LIMIT
#     # jrieke: 6 seconds, 16 API calls
#     # chrieke: 8 seconds, 19 API calls
#     # tiangolo: 53 seconds, 124 API calls

#     # if stargazers_count < 0:
#     # METHOD 1: PAGES (with an S)
#     # jrieke: 6 seconds, 15 API calls
#     # chrieke: 7 seconds, 34 API calls
#     # tiangolo: 280 API calls, GIVES ERRORS OR STOPS
#     #     print(" -> Using counting")
#     #     new_stars_per_repo[repo_name] = _find_stars_via_counting(
#     #         username, repo_name, stargazers_count, year
#     #     )
#     # else:

#     # METHOD 3: BINARY SEARCH
#     # jrieke: 6 seconds, 16 API calls
#     # chrieke: 10 seconds, 19 API calls
#     # tiangolo: 55 seconds, 94 API calls
#     print(" -> binary search")
#     # TODO: Maybe pass full_name to the search method directly.
#     new_stars_per_repo[full_name] = _find_stars_via_binary_search(
#         *full_name.split("/"), stargazers_count, year
#     )

#     print("Took", time.time() - stars_start_time)
#     print()

#     # TODO: Use stargazers_count to calculate more accurate progress.
#     progress = 0.2 + 0.8 * ((i + 1) / len(repos_to_inspect))
#     yield summary_stats(), progress, progress_msg(i + 1)

# # TODO: Maybe do API calls in parallel like below. Seems to speed things up
# # a bit on local computer (especially for large repos) but needs to be tested on
# # server. Cons: Makes progress bar/text more difficult; harder to debug;
# # might lead to problems if too many jobs are run at the same time.
# # new_stars_list = Parallel(n_jobs=21)(
# #     delayed(_find_stars_via_binary_search)(
# #         username, repo_name, stargazers_count, year
# #     )
# #     for repo_name, stargazers_count in repos_to_inspect
# # )
# # new_stars_per_repo = dict(zip(repos_to_inspect, new_stars_list))

# if verbose:
#     print(f"New repos: {new_repos}")
#     print(f"New stars per repo: {new_stars_per_repo}")
#     print(f"New stars: {new_stars}")
#     print(f"Hottest repo (+{hottest_new_stars} stars): {hottest_full_name}")


# def _find_stars_via_counting(username, repo_name, stargazers_count, year):
#     """Returns the number of stars in a year by counting all the ones in that year."""

#     # Calculate number of pages. Each page has 100 items.
#     num_pages = 1 + int(stargazers_count / 100)  # round up

#     # Retrieve all pages. This automatically inserts per_page=100.
#     # TODO: This here is the bottleneck where it stops sometimes if there are many
#     # stars/pages.
#     # TODO: In any way, make a timeout here!!
#     retrieved_pages = pages(
#         api.activity.list_stargazers_for_repo,
#         num_pages,
#         username,
#         repo_name,
#         headers={"Accept": "application/vnd.github.v3.star+json"},
#     )
#     print("Retrieved pages", end="")
#     concat_pages = retrieved_pages.concat()
#     print(", concatenated, iterating: ", end="")

#     # Iterate through all pages and count new stars.
#     new_stars = 0
#     for stargazer in concat_pages:
#         # for stargazer in stargazers:
#         # print(stargazer)
#         print(".", end="")
#         if int(stargazer.starred_at[:4]) == year:
#             new_stars += 1
#     print()

#     return new_stars
