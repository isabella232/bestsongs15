#!/usr/bin/env python

"""
Commands that update or process the application data.
"""
import app_config
import codecs
import copytext
import csv
import json
import os
import requests
import spotipy

from datetime import datetime
from fabric.api import task
from facebook import GraphAPI
from oauth import get_document
from rdioapi import Rdio
from smartypants import smartypants
from twitter import Twitter, OAuth

SONGS_SPREADSHEET_URL_TEMPLATE = 'https://docs.google.com/feeds/download/spreadsheets/Export?exportFormat=csv&key=%s'

@task(default=True)
def update():
    """
    Stub function for updating app-specific data.
    """
    #update_featured_social()
    update_songs()

@task
def update_songs(verify='true'):
    get_document(app_config.SONGS_GOOGLE_DOC_KEY, app_config.SONGS_DATA_PATH)
    data = copytext.Copy(app_config.SONGS_DATA_PATH)

    output = process_songs(data, verify == 'true')

    with codecs.open('data/songs.json', 'w', 'utf-8') as f:
        json.dump(output, f)

@task
def process_songs(data, verify):

    tagdata = copytext.Copy(app_config.COPY_PATH)['tags']._serialize()
    genre_tags = [tag['displayname'] for tag in tagdata.values()]

    output = []
    unique_audio = []
    unique_song_art = []
    unique_song_title = []

    songs = data['songs']._serialize()
    reviews = data['reviews']._serialize()

    for song in songs:
        for name, value in song.items():
            try:
                song[name] = value.strip()
            except AttributeError:
                pass

        print '%s - %s' % (song['artist'], song['title'])

        if song['song_art']:
            name, ext = os.path.splitext(song['song_art'])
            song['song_art'] = '%s-s500%s' % (name, ext)

        if song['title']:
            song['title'] = smartypants(song['title'])

        if song['artist']:
            song['artist'] = smartypants(song['artist'])

        if song['featured'] == 'True':
            song['featured'] = True
        else:
            song['featured'] = False

        tags = []

        for tag in song['genre_tags'].split(','):
            tag = tag.strip()
            defined_tag = tagdata.get(tag)
            if defined_tag:
                tags.append(defined_tag['displayname'])
            elif not defined_tag and verify:
                print "--> Tag %s is not a valid tag" % (tag)

        song['genre_tags'] = tags

        song['reviews'] = []
        for review in reviews:
            if song['id'] == review['id']:
                review['review'] = smartypants(review['review'])
                song['reviews'].append(review)

        if verify:
            # Verify links
            try:
                audio_link = 'http://pd.npr.org/anon.npr-mp3%s.mp3' % song['media_url']
                audio_request = requests.head(audio_link)

                if audio_request.status_code != 200:
                    print '--> %s The audio URL is invalid: %s' % (audio_request.status_code, audio_link)

                song_art_link = 'http://www.npr.org%s' % song['song_art']
                song_art_request = requests.head(song_art_link)

                if song_art_request.status_code != 200:
                    print '--> %s The song art URL is invalid: %s' % (song_art_request, song_art_link)
            except:
                print '--> request.head failed'

            if song['media_url'] in unique_audio:
                print '--> Duplicate audio url: %s' % song['media_url']
            else:
                unique_audio.append(song['media_url'])

            if song['song_art'] in unique_song_art:
                print '--> Duplicate song_art url: %s' % song['song_art']
            else:
                unique_song_art.append(song['song_art'])

            if song['title'] in unique_song_title:
                print '--> Duplicate title: %s' % song['title']
            else:
                unique_song_title.append(song['title'])

        output.append(song)

    return output


@task
def generate_rdio_playlist():
    """
    Generate a list of Rdio track IDs
    """

    secrets = app_config.get_secrets()
    state = {}
    rdio_api = Rdio(
        secrets['RDIO_CONSUMER_KEY'],
        secrets['RDIO_CONSUMER_SECRET'],
        state
    )
    songs = []

    with open('data/songs.csv') as f:
        rows = csv.DictReader(f)

        for row in rows:
            if row['rdio']:
                song_object = rdio_api.getObjectFromUrl(url=row['rdio'])
                if song_object['type'] == 't':
                    songs.append(song_object['key'])

    print ','.join(songs)

@task
def generate_spotify_playlist():
    """
    Generate a list of Spotify track IDs
    """

    sp = spotipy.Spotify()
    songs = []
    secrets = app_config.get_secrets()

    with open('data/songs.csv') as f:
        rows = csv.DictReader(f)

        for row in rows:
            if row['spotify'] and "track" in row['spotify']:
                try:
                    song_object = sp.track(track_id=row['spotify'])
                    if song_object['track_number']:
                        songs.append(song_object['uri'])
                except:
                    print 'invalid ID'

    print ','.join(songs)

@task
def update_featured_social():
    """
    Update featured tweets
    """
    COPY = copytext.Copy(app_config.COPY_PATH)
    secrets = app_config.get_secrets()

    # Twitter
    print 'Fetching tweets...'

    twitter_api = Twitter(
        auth=OAuth(
            secrets['TWITTER_API_OAUTH_TOKEN'],
            secrets['TWITTER_API_OAUTH_SECRET'],
            secrets['TWITTER_API_CONSUMER_KEY'],
            secrets['TWITTER_API_CONSUMER_SECRET']
        )
    )

    tweets = []

    for i in range(1, 4):
        tweet_url = COPY['share']['featured_tweet%i' % i]

        if isinstance(tweet_url, copytext.Error) or unicode(tweet_url).strip() == '':
            continue

        tweet_id = unicode(tweet_url).split('/')[-1]

        tweet = twitter_api.statuses.show(id=tweet_id)

        creation_date = datetime.strptime(tweet['created_at'],'%a %b %d %H:%M:%S +0000 %Y')
        creation_date = '%s %i' % (creation_date.strftime('%b'), creation_date.day)

        tweet_url = 'http://twitter.com/%s/status/%s' % (tweet['user']['screen_name'], tweet['id'])

        photo = None
        html = tweet['text']
        subs = {}

        for media in tweet['entities'].get('media', []):
            original = tweet['text'][media['indices'][0]:media['indices'][1]]
            replacement = '<a href="%s" target="_blank" onclick="_gaq.push([\'_trackEvent\', \'%s\', \'featured-tweet-action\', \'link\', 0, \'%s\']);">%s</a>' % (media['url'], app_config.PROJECT_SLUG, tweet_url, media['display_url'])

            subs[original] = replacement

            if media['type'] == 'photo' and not photo:
                photo = {
                    'url': media['media_url']
                }

        for url in tweet['entities'].get('urls', []):
            original = tweet['text'][url['indices'][0]:url['indices'][1]]
            replacement = '<a href="%s" target="_blank" onclick="_gaq.push([\'_trackEvent\', \'%s\', \'featured-tweet-action\', \'link\', 0, \'%s\']);">%s</a>' % (url['url'], app_config.PROJECT_SLUG, tweet_url, url['display_url'])

            subs[original] = replacement

        for hashtag in tweet['entities'].get('hashtags', []):
            original = tweet['text'][hashtag['indices'][0]:hashtag['indices'][1]]
            replacement = '<a href="https://twitter.com/hashtag/%s" target="_blank" onclick="_gaq.push([\'_trackEvent\', \'%s\', \'featured-tweet-action\', \'hashtag\', 0, \'%s\']);">%s</a>' % (hashtag['text'], app_config.PROJECT_SLUG, tweet_url, '#%s' % hashtag['text'])

            subs[original] = replacement

        for original, replacement in subs.items():
            html =  html.replace(original, replacement)

        # https://dev.twitter.com/docs/api/1.1/get/statuses/show/%3Aid
        tweets.append({
            'id': tweet['id'],
            'url': tweet_url,
            'html': html,
            'favorite_count': tweet['favorite_count'],
            'retweet_count': tweet['retweet_count'],
            'user': {
                'id': tweet['user']['id'],
                'name': tweet['user']['name'],
                'screen_name': tweet['user']['screen_name'],
                'profile_image_url': tweet['user']['profile_image_url'],
                'url': tweet['user']['url'],
            },
            'creation_date': creation_date,
            'photo': photo
        })

    # Facebook
    print 'Fetching Facebook posts...'

    fb_api = GraphAPI(secrets['FACEBOOK_API_APP_TOKEN'])

    facebook_posts = []

    for i in range(1, 4):
        fb_url = COPY['share']['featured_facebook%i' % i]

        if isinstance(fb_url, copytext.Error) or unicode(fb_url).strip() == '':
            continue

        fb_id = unicode(fb_url).split('/')[-1]

        post = fb_api.get_object(fb_id)
        user  = fb_api.get_object(post['from']['id'])
        user_picture = fb_api.get_object('%s/picture' % post['from']['id'])
        likes = fb_api.get_object('%s/likes' % fb_id, summary='true')
        comments = fb_api.get_object('%s/comments' % fb_id, summary='true')
        #shares = fb_api.get_object('%s/sharedposts' % fb_id)

        creation_date = datetime.strptime(post['created_time'],'%Y-%m-%dT%H:%M:%S+0000')
        creation_date = '%s %i' % (creation_date.strftime('%b'), creation_date.day)

        # https://developers.facebook.com/docs/graph-api/reference/v2.0/post
        facebook_posts.append({
            'id': post['id'],
            'message': post['message'],
            'link': {
                'url': post['link'],
                'name': post['name'],
                'caption': (post['caption'] if 'caption' in post else None),
                'description': post['description'],
                'picture': post['picture']
            },
            'from': {
                'name': user['name'],
                'link': user['link'],
                'picture': user_picture['url']
            },
            'likes': likes['summary']['total_count'],
            'comments': comments['summary']['total_count'],
            #'shares': shares['summary']['total_count'],
            'creation_date': creation_date
        })

    # Render to JSON
    output = {
        'tweets': tweets,
        'facebook_posts': facebook_posts
    }

    with open('data/featured.json', 'w') as f:
        json.dump(output, f)
