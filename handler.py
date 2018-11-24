import requirements
from PIL import Image

import boto3
import os
import urllib.request
import json
import logging
import random
import re
import io


logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('rekognition','ap-northeast-1')

ignore_word = ['Animal', 'Pet', 'Mammal', 'Wildlife']


def post_simple_msg_to_slack_ch(msg: str, ch: str, oauth_token: str, bot_token: str):
    # chat.postMessage API
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": "Bearer {0}".format(bot_token)
    }
    data = {
        "token": oauth_token,
        "channel": ch,
        "text": msg,
        "username": "Image-Recognition-and-Movie-Recommend-Bot"
    }

    logging.info('try send...')
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST", headers=headers)
    urllib.request.urlopen(req)
    logging.info('send done')

    return


def post_msg_to_slack_ch(label: str, ch: str, oauth_token: str, bot_token: str, movie_db_token: str):
    movie_info = get_movie_with_label(label, movie_db_token)
    if movie_info == None:
        post_simple_msg_to_slack_ch("Error: no matched keywrod with " + label, ch, oauth_token, bot_token)
        return

    movie_url = 'https://www.themoviedb.org/movie/' + str(movie_info['id'])
    movie_img_url = "https://image.tmdb.org/t/p/w500" + movie_info['poster_path']
    msg = 'I can see: ' + label + '\n  related movie: ' +  movie_url

    # chat.postMessage API
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": "Bearer {0}".format(bot_token)
    }
    data = {
        "token": oauth_token,
        "channel": ch,
        "text": msg,
        "username": "Image-Recognition-and-Movie-Recommend-Bot",
        "attachments": json.dumps([
            {
                "title": movie_info['title'],
                "image_url": movie_img_url
            }
        ])
    }

    logging.info('try send...')
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST", headers=headers)
    urllib.request.urlopen(req)
    logging.info('send done')

    return


def get_movie_with_label(label: str, movie_db_token: str):
    # get keyword id
    search_keyword_url = 'https://api.themoviedb.org/3/search/keyword?api_key=' + movie_db_token + '&query=' + label
    logging.info('search keyword query: ' + search_keyword_url)
    req_keyword = urllib.request.Request(search_keyword_url)
    with urllib.request.urlopen(req_keyword) as res:
        body = json.loads(res.read())
        logging.info('search keyword')
        logging.info(body)
        if not body['results']:
            logging.info('no keyword matched')
            return None
        else:
            top_keyword_id = str(body['results'][0]['id'])
    
    # get popular movie with keyword id
    discover_movie_url = 'https://api.themoviedb.org/3/discover/movie?api_key=' + movie_db_token + '&with_keywords=' + top_keyword_id
    logging.info('discover movie query: ' + discover_movie_url)
    req_movie = urllib.request.Request(discover_movie_url)
    with urllib.request.urlopen(req_movie) as res:
        body = json.loads(res.read())
        random_num = random.randrange(min([20, body['total_results']]))
        logging.info('discover movie: use ' + str(random_num) + 'th result')
        logging.info(body)
        top_movie = body['results'][random_num]

    return top_movie


def is_bot(event: dict) -> bool:
    if 'subtype' in event:
        return event['subtype'] == "bot_message"
    else:
        return False


def is_msg_event(event: dict) -> bool:
    #return event['type'] == "message"
    return event['type'] == "app_mention"


def main(event, context):
    # get env var
    OAUTH_TOKEN = os.environ['OAUTH_TOKEN']
    BOT_TOKEN = os.environ['BOT_TOKEN']
    MOVIE_DB_TOKEN = os.environ['MOVIE_DB_TOKEN']

    ## for challenge and response authentication
    ebody = json.loads(event['body'])
    logging.info(json.dumps(event))
    logging.info(json.dumps(ebody))
    if 'challenge' in ebody:
        return {
            "statusCode": 200,
            "body": ebody['challenge']
        }

    ## for non-related event (bot msg, non msg event, or retry event)
    slack_event = ebody['event']
    if is_bot(slack_event) or not is_msg_event(slack_event) or 'X-Slack-Retry-Num' in event['headers']:
        logging.info('non-target event')
        return {
            "statusCode": 200,
            "body": "Non-target event" 
        }

    if 'text' in slack_event and 'channel' in slack_event:
        # extract img url from mention msg
        img_url = re.sub(r'<@.*?>', '', slack_event['text']).replace('<', '').replace('>', '').strip()
        logging.info(img_url)

        # save img locally
        try:
            with urllib.request.urlopen(img_url) as url:
                with open('/tmp/temp.jpg', 'wb') as f:
                    f.write(url.read())
        except urllib.error.URLError as err:
            # http access error handling
            logging.info(err)
            post_simple_msg_to_slack_ch("Error in downloading img", slack_event['channel'], OAUTH_TOKEN, BOT_TOKEN)

        # detect label with Amazon Rekognition
        with open('/tmp/temp.jpg', 'rb') as image:
            res = client.detect_labels(Image={'Bytes': image.read()})
            logging.info(res['Labels'])

        for l in res['Labels']:
            label = l['Name']
            if not label in ignore_word:
                ## if not ignore word, post msg
                post_msg_to_slack_ch(label, slack_event['channel'], OAUTH_TOKEN, BOT_TOKEN, MOVIE_DB_TOKEN)
                break

    logging.info('DONE')
    return {
        "statusCode": 200,
        "headers": {"X-Slack-No-Retry": 1},
        "body": "Success" 
    }
