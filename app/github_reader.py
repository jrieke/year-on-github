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
import functools
import random

from dotenv import load_dotenv
import requests
from fastcore.net import HTTP404NotFoundError
import fastcore.net
import streamlit as st
from ghapi.core import GhApi
from ghapi.page import pages

import utils


# Monkey-patch ghapi/fastcore. This makes it raise a timeout error if an API request
# through ghapi takes too long. Timeouts can happen sometimes when a user has lots of
# repos.
fastcore.net._opener.open = functools.partial(fastcore.net._opener.open, timeout=15)


# Set up the Github REST API client.
# Note that ghapi contains a bug in the `paged` method as of December 2020, therefore
# it's safer to install my fork (see README.md for instructions).
load_dotenv()
if os.getenv("GH_TOKENS"):
    GH_TOKENS = os.getenv("GH_TOKENS").split(",")
    print(f"Found {len(GH_TOKENS)} token(s) for Github API")
else:
    raise RuntimeError(
        "Couldn't find a token for Github API! Specify via env variable GH_TOKENS"
    )

api = GhApi(
    token=random.choice(GH_TOKENS),
    limit_cb=lambda rem, quota: print(f"Quota remaining: {rem} of {quota}"),
)


def switch_api_token():
    """Update API to use a new, random token from the env variable GH_TOKENS."""
    api.headers["Authorization"] = f"token {random.choice(GH_TOKENS)}"
    print("Switched API token")


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


class TimeoutError(Exception):
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
        switch_api_token()
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
    contributor_names = set()  # only used if is_org is True
    contributors_greater_than = False
    endpoint = api.repos.list_for_org if is_org else api.repos.list_for_user
    num_pages = 1 + int(num_repos / 100)
    switch_api_token()
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

        # For orgs: Count number of contributors across all repos.
        # TODO: For large orgs, this can take a significant amount of time. Should show
        #   progress in more detail here.
        if is_org:
            year_start = datetime(year, 1, 1, 0, 0, 0)
            year_end = datetime(year, 12, 31, 23, 59, 59)
            repo_contributor_names = set()
            # TODO: This only returns the 100 most active contributors and there's no
            #   way to get more, i.e. it doesn't work for very popular repos. Maybe look for
            #   another way to do this.
            switch_api_token()
            contributors = api.repos.get_contributors_stats(repo.owner.login, repo.name)
            if len(contributors) == 100:
                contributors_greater_than = True
            for contributor in contributors:
                # print(
                #     f"Analyzing contributor f{contributor.author.login} ({contributor.total} contributions)"
                # )
                for week_stats in contributor.weeks:
                    week = datetime.fromtimestamp(int(week_stats.w))
                    if week_stats.c > 0 and week > year_start and week < year_end:
                        # print(f"Found {week_stats.c} contributions in week {week}")
                        # print()
                        repo_contributor_names.add(contributor.author.login)
                        break
            print(f"Found {len(repo_contributor_names)} contributors")
            contributor_names |= repo_contributor_names

        print()

    # 3) Query GraphQL API to get contribution counts + external repos.
    if is_org:
        contributions = 0
        # TODO: Temporarily storing this in `repos_contributed_to`, rename if I keep it.
        repos_contributed_to = len(contributor_names)
        if contributors_greater_than:
            repos_contributed_to = ">" + str(repos_contributed_to)
        external_repo_stars = {}
    else:
        url = "https://api.github.com/graphql"
        if "Authorization" in api.headers:
            headers = {"Authorization": api.headers["Authorization"]}
        else:
            headers = {}
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
    
    print(full_name)

    def get_stargazers(page: int):
        """Retrieves a page of stargazers from the Github API."""
        switch_api_token()
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
        print()
        return new_stars
    elif new_stars > 0 and new_stars < len(stargazers):  # break is on first page
        print("Found year break on first page")

        # Add all stars on the last page.
        new_stars += len(get_stargazers(num_pages))

        # Add 100 stars for each page in between.
        if num_pages > 2:
            new_stars += (num_pages - 2) * 100

        print("Total new stars:", new_stars)
        print()
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
        print()
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
        self.external_repos = list(self.external_repo_stars.keys())

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
            # print(repo)
            new_stars = _query_repo(repo, self.year)
            # print()

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
            hottest_repo_stars = max(all_repo_stars.items(), key=lambda item: item[1])
            hottest = f"{hottest_repo_stars[0]} (+{hottest_repo_stars[1]})"
        elif len(all_repo_stars) > 0:
            # If no new stars, just choose the first repo (and do not display stars).
            # TODO: Choose repo with most stars overall. But need to save this somewhere
            #    above, otherwise it would mean a lot of API calls here (as this is
            #    called after each queried repo).
            hottest = list(all_repo_stars.keys())[0]
        else:
            # No repos at all.
            hottest = "No repos yet :)"

        stats = {
            "username": self.username,
            # "avatar_url": avatar_url,
            "is_org": self.is_org,
            "contributions": self.contributions,
            "repos_contributed_to": self.repos_contributed_to,
            # "new_repos": new_repos,
            "new_stars": new_stars,
            # "hottest_name": hottest_name,
            "hottest": hottest,
            # "external_repos": external_repos,
        }
        return stats
