import requirements
from PIL import Image

import boto3
import os
import urllib.request
import json
import logging
import re
import io


logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('rekognition','ap-northeast-1')


def post_msg_to_slack_ch(msg: str, ch: str, oauth_token: str, bot_token: str):
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
        "username": "Bot-Sample"
    }

    logging.info('try send...')
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST", headers=headers)
    urllib.request.urlopen(req)
    logging.info('send done')

    return


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
    # HOOK_KEYWORD = os.environ['HOOK_KEYWORD']
    # REPLY_WORD = os.environ['REPLY_WORD']
    # BOT_NAME = os.environ['BOT_NAME']

    #logging.info(json.dumps(event))

    ## for challenge and response authentication
    ebody = json.loads(event['body'])
    logging.info(json.dumps(ebody))
    if 'challenge' in ebody:
        return {
            "statusCode": 200,
            "body": ebody['challenge']
        }

    ## for non-related event (bot msg or non msg event)
    slack_event = ebody['event']
    if is_bot(slack_event) or not is_msg_event(slack_event):
        logging.info('non-target event')
        return {
            "statusCode": 200,
            "body": "Non-target event" 
        }

    ## post msg
    if 'text' in slack_event and 'channel' in slack_event:
        img_url = re.sub(r'<@.*?>', '', slack_event['text']).replace('<', '').replace('>', '').strip()
        logging.info(img_url)

        #with urllib.request.urlopen(img_url) as url:
        #    f = io.BytesIO(url.read())
        with urllib.request.urlopen(img_url) as url:
            with open('/tmp/temp.jpg', 'wb') as f:
                f.write(url.read())

        #img = Image.open(f)
        #res = client.detect_labels(Image={'Bytes': f})

        with open('/tmp/temp.jpg', 'rb') as image:
            res = client.detect_labels(Image={'Bytes': image.read()})

        logging.info(res['Labels'])

        post_msg_to_slack_ch("I can see: " + res['Labels'][0]['Name'], slack_event['channel'], OAUTH_TOKEN, BOT_TOKEN)

    logging.info('DONE')
    return {
        "statusCode": 200,
        "body": "Success" 
    }
