# My year on Github 🧑‍💻

[![Heroku App Status](http://heroku-shields.herokuapp.com/my-year-on-github)](http://gh2020.jrieke.com)

**Share your Github stats for 2020 on Twitter.**

This project contains a small web app that let's you share stats about your Github activity from last year. It's like Spotify's "year in review" but for Github. The app is built with [Streamlit](https://www.streamlit.io/), queries Github's API via [ghapi](https://ghapi.fast.ai/), and let's you share the generated stats directly on [Twitter](https://twitter.com/).

*🚀 Try it out: [gh2020.jrieke.com](http://gh2020.jrieke.com/) 🚀*

<p align="center">
    <a href="http://gh2020.jrieke.com/"><img src="images/preview.png" width=500></a>
</p>

---

<br>

**Note: The steps below are only required if you want to work on the app. If you just want to use it, go [here](http://gh2020.jrieke.com/).**

## Installation

```bash
git clone https://github.com/jrieke/my-year-on-github
cd my-year-on-github
pip install -r requirements.txt
```

Note that [ghapi](https://ghapi.fast.ai/) has (as of 26 December 2020) a small bug which causes problems, therefore the commands above will install it from [my fork](https://github.com/jrieke/ghapi) (you can also install it manually from there with `pip install -U git+https://github.com/jrieke/ghapi`).

Requires Python 3, tested with 3.7.6.


## Running locally

```bash
streamlit run app/main.py
```

Make sure to run always from the `my-year-on-github` dir (not from the `app `dir), otherwise the app will not be able to find the css file.

## Deploying to Heroku

First, [install heroku and login](https://devcenter.heroku.com/articles/getting-started-with-python#set-up). 
To create a new deployment, run inside `my-year-on-github`:

```
heroku create
git push heroku main
heroku open
```

To update the deployed app, commit your changes and run:

```
git push heroku main
```