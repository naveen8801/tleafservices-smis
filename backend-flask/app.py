from flask import Flask, jsonify, request
from flask_cors import CORS
import tweepy
import random
from datetime import datetime
from datetime import timedelta
import time
from flask_pymongo import PyMongo
import re
from PredictbyRules import predictByRules, stopWordsRemove, lemitizeWords, CleanBody
from PredictSentiment import TellmeSentiment
from TweepyStream import TwitterStream
from bson.objectid import ObjectId
import os

os.environ['OPENBLAS_NUM_THREADS'] = '1'

import numpy as np

app = Flask(__name__)
CORS(app)
app.config[
    "MONGO_URI"
] = ""
mongo = PyMongo(app)
db = mongo.db

# .env setup
# APP_ROOT = os.path.join(os.path.dirname(__file__) + "/Twitter Scraping Script", "..")
# dotenv_path = os.path.join(APP_ROOT, ".env")
# load_dotenv(dotenv_path)

API_KEY = ""
API_SECRET_KEY = ""
BEARER_TOKEN = ""
ACCESS_TOKEN = ""
ACCESS_TOKEN_SECRET = ""

twpy_qry = "(@mpdial100) OR (@PoliceIndore) OR (@dgp_mp) OR (@bhopal_police) OR (@igp_bhopal_mp) OR (@MpPoliceOffici1) \
    OR (Madhya AND Pradesh AND Police) OR (Indore AND police) OR (Bhopal AND Police) OR (Jabalpur AND Police) \
    OR (Burhanpur AND Police) OR (Khandwa AND Police) OR (Ujjain AND Police) OR (Dhar AND Police) OR (Harda AND Police) \
    OR (Gwalior AND Police) OR (Hoshangabad AND Police) OR (Ratlam AND Police) OR (Hoshangabad AND Police) OR (Seoni AND Police)  -filter:retweets AND filter:replies"

qry_list = [
    "(Madhya AND Pradesh AND Police) OR (Indore AND police) OR (Bhopal AND Police) OR (Jabalpur AND Police) \
                OR (Burhanpur AND Police) OR (Khandwa AND Police) OR (Ujjain AND Police) OR (Dhar AND Police) OR (Harda AND Police) \
                OR (Gwalior AND Police) OR (Hoshangabad AND Police) OR (Ratlam AND Police) OR (Hoshangabad AND Police) OR (Seoni AND Police)  -filter:retweets AND filter:replies",
    "(@mpdial100) OR (@PoliceIndore) OR (@dgp_mp) OR (@bhopal_police) OR (@igp_bhopal_mp) OR (@MpPoliceOffici1)  -filter:retweets AND filter:replies",
]

stram_qry_lst = ["Madhya Pradesh AND Police", "Indore AND police","Bhopal AND Police","Jabalpur AND Police","Burhanpur AND Police","Khandwa AND Police","Ujjain AND Police","Ratlam AND Police","Harda AND Police","Gwalior AND Police"]

# Tweepy Setup
auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

start_time = time.time()
prevfetch_time = time.time()

now = datetime.today().now()
prev = now - timedelta(hours=1)
sinceDate = prev.strftime("%Y-%m-%d")

alert = ["True", "False"]

streams = []

def RemoveMentionsFromTweetText(text):
    new_text = re.sub("@[A-Za-z0-9_]+", "", text)
    return new_text.strip()


def NewFetchTweetsFucntion(sincedate , qry_list):
    d = []
    for qry in qry_list:
        c = tweepy.Cursor(
            api.search,
            q=qry,
            lang="en",
            count=100,
            since=sincedate,
            tweet_mode="extended",
        )
        for tweet in c.items():
            tweet_id = tweet.id_str
            img = tweet.user.profile_image_url
            Date = tweet.created_at.strftime("%Y-%m-%d %H:%M:%S")
            User_Name = tweet.user.screen_name
            text = (
                tweet.full_text.replace("\\n", " ")
                    .replace("\\r", " ")
                    .replace("\\r\\n", " ")
                    .replace("\n", " ")
                    .replace("\r", " ")
            )
            withoutCommentandHashtags = RemoveMentionsFromTweetText(text)
            cleaned_text = CleanBody(text)
            cleaned_text = lemitizeWords(cleaned_text)
            cleaned_text = stopWordsRemove(cleaned_text)
            type = predictByRules(cleaned_text)
            likes = tweet.favorite_count
            user_location = tweet.user.location
            if tweet.coordinates is not None:
                long = tweet.coordinates["coordinates"][0]
                lat = tweet.coordinates["coordinates"][1]
            else:
                long = None
                lat = None
            d.append(
                {
                    'img': img,
                    '_id': tweet_id,
                    'Date': Date,
                    'handle': User_Name,
                    'text': text,
                    'likes': likes,
                    'type': type,
                    'sentiment': TellmeSentiment(withoutCommentandHashtags),
                    'alert' : random.choice(alert),
                    'user_location': user_location,
                    'long': long,
                    'lat': lat,
                }
            )
    d.sort(key=lambda x: x["Date"])
    d.reverse()
    return d


@app.route("/")
def hello_world():
    return "Deployed on Azure"

@app.route("/update-search-keywords",methods=['POST', 'GET'])
def update_search_keywords():
    user_id = "61404dc33c0c7172c241f734"
    if request.method == 'POST':
        data = request.get_json()
        keywords = data['keywords']
        db['keywords'].update_one({'_id' : ObjectId(user_id)}, {"$set": {'keywords' : keywords}})
        # ["(Madhya AND Pradesh AND Police) OR (Indore AND police) OR (Bhopal AND Police) OR (Jabalpur AND Police) OR (Burhanpur AND Police) OR (Khandwa AND Police) OR (Ujjain AND Police) OR (Dhar AND Police) OR (Harda AND Police) OR (Gwalior AND Police) OR (Hoshangabad AND Police) OR (Ratlam AND Police) OR (Hoshangabad AND Police) OR (Seoni AND Police)  -filter:retweets AND filter:replies", "(@mpdial100) OR (@PoliceIndore) OR (@dgp_mp) OR (@bhopal_police) OR (@igp_bhopal_mp) OR (@MpPoliceOffici1)  -filter:retweets AND filter:replies"]
        return jsonify({
            'status' : 200
        })
    if request.method == 'GET':
        keywords = db['keywords'].find_one({'_id' : ObjectId(user_id)})['keywords']
        return jsonify({
            'status' : 200,
            'keywords' : keywords
        })

@app.route("/data")
def get_data():
    days = request.args.get('days')
    now = datetime.today().now()
    prev = now - timedelta(days=int(days))
    sinceDate = prev.strftime("%Y-%m-%d %H:%M:%S")

    # example - http://127.0.0.1:5000/data?days=1

    tweets = db['realtime-data'].find()

    main = []
    for p in tweets:
        if (p['Date'] > sinceDate):
            main.append(p)

    main.sort(key=lambda x: x["Date"])
    main.reverse()

    tweets_cleaned = []
    for x in main:
        x['text'] = re.sub("@[A-Za-z0-9_]+", "", x['text'])
        x['text'] = x['text'].strip()
        tweets_cleaned.append(x)

    return jsonify(tweets_cleaned)


@app.route("/fetch-latest")
def fetch_latest():
    now = datetime.today().now()
    prev = now - timedelta(hours=12)
    sinceDate = prev.strftime("%Y-%m-%d")

    # Getting user keywords
    user_id = "61404dc33c0c7172c241f734"
    userkeywords = db['keywords'].find_one({'_id' : ObjectId(user_id)})['keywords']
    print(userkeywords)

    # Fetching Tweets
    tweets = NewFetchTweetsFucntion(sinceDate , userkeywords)
    print("Tweets fetched !")

    # Removing Mentions and Hashtags
    tweets_cleaned = []
    for x in tweets:
        x['text'] = re.sub("@[A-Za-z0-9_]+","", x['text'])
        x['text'] = x['text'].strip()
        tweets_cleaned.append(x)
    print("@ Removed foe sending to UI")

    # Getting unique tweets from fetched tweets
    unique_tweets = list({v['_id']: v for v in tweets}.values())
    print("Unique tweets identified !")
    print("Unique tweets : " + str(len(unique_tweets)))


    # Saving data to mongoDB
    for tweet in unique_tweets:
        db['realtime-data'].update_one({'_id': tweet['_id']}, {"$set": tweet}, upsert=True)
    print("Data Saved To Database  Successfully !")


    return jsonify(tweets_cleaned)


@app.route("/login", methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data['username']
        password = data['password']
        if username == "smdemo" and password == "mpPolice":
            return jsonify({
                'user_id' : 1,
                'status': 200
            })
        if username == "smdemo2" and password == "mpPolice":
            return jsonify({
                'user_id' : 2,
                'status': 200
            })
        else:
            return jsonify({
                'status': 404
            })

@app.route("/stream")
def stream():
    for stream in streams:
        stream.disconnect()
    listener = TwitterStream()
    streamer = tweepy.Stream(auth=auth, listener=listener, tweet_mode='extended')
    streams.append(streamer)
    streamer.filter(track=["politics","modi","rahul gandhi"])
    return "done"

if __name__ == "__main__":
    app.run()
