# -*- coding: utf-8 -*-
import subprocess

import requests
import re
import json
from tqdm import tqdm
import os
import sys
import eyed3
import ffmpy

reload(sys)
sys.setdefaultencoding('utf-8')

REG = {
    'ul': re.compile(r'^.*listWrap.*?<ul class="clr">(.*?)</ul>.*$', re.S),
    'li': re.compile(r'(<li.*?</li>)', re.S),
    'info': re.compile(r'<li id="(.*?)" data-week="(.*?)" data-genre="(.*?)" data-update="(.*?)" data-kana="(.*?)"'
                       r'(?: data-guest=")?(.*?)"? class="(.*?)">'
                       r'.*?'
                       r'<h4.*?span>(.*?)</span'
                       r'.*?'
                       r'navigator.*?span>(.*?)</span'
                       r'.*', re.S)
}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/65.0.3325.181 Safari/537.36'
}

if __name__ == '__main__':
    s = requests.session()
    s.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
    s.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
    s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'})
    resp = s.get('http://www.onsen.ag/')
    playlist = {}
    if not os.path.exists('data'):
        os.mkdir('data')
    if os.path.exists(os.path.join('data', 'list.json')):
        with open(os.path.join('data', 'list.json'), 'r') as f:
            playlist = json.load(f)
    m = REG['ul'].match(resp.content)
    # Fetch
    if m is not None:
        ul = m.group(1)
        it = REG['li'].finditer(ul)
        for li in it:
            info = REG['info'].match(li.group(1))
            if info is not None:
                bid = info.group(1).decode('utf-8')
                item = {
                    u'week': info.group(2).decode('utf-8'),
                    u'genre': info.group(3).decode('utf-8'),
                    u'update': info.group(4).decode('utf-8'),
                    u'kana': info.group(5).decode('utf-8'),
                    u'guest': info.group(6).decode('utf-8'),
                    u'class': info.group(7).decode('utf-8'),
                    u'title': info.group(8).decode('utf-8'),
                    u'personality': info.group(9).decode('utf-8'),
                    u'uploaded': u'False'
                }
                if u'noMovie' in item[u'class']:
                    print u'Skip ' + bid + u' - ' + item[u'title'] + u': Bangumi is unavailable'
                    continue
                api = u'http://www.onsen.ag/data/api/getMovieInfo/' + bid
                resp = s.get(api)
                movieInfo = json.loads(resp.content[9: -3])
                item[u'remoteFile'] = movieInfo['moviePath']['pc']
                item[u'remoteThumbnail'] = u'http://www.onsen.ag' + movieInfo['thumbnailPath'].replace('_m.', '_l.')
                filename = item[u'remoteFile'].split('/')[-1]
                fid = filename.split('.')[0]
                item[u'localFile'] = os.path.join('data', bid, filename).decode('utf-8')
                item[u'localThumbnail'] = os.path.join('data', bid, item[u'remoteThumbnail'].split('/')[-1])
                item[u'type'] = item[u'localFile'].split(u'.')[-1]
                if bid in playlist and fid in playlist[bid]:
                    print u'Skip ' + item[u'localFile'] + u': File exists in list file'
                    continue
                if not os.path.exists(os.path.join('data', bid)):
                    os.mkdir(os.path.join('data', bid))
                    print u'Writing to data\\' + bid + u'\\' + item[u'remoteThumbnail'].split('/')[-1] + u'...'
                    with open(item[u'localThumbnail'], 'wb') as f:
                        url = u'http://www.onsen.ag' + item[u'remoteThumbnail']
                        resp = s.get(item[u'remoteThumbnail'], stream=True, timeout=30)
                        for chunk in tqdm(resp.iter_content()):
                            f.write(chunk)
                print u'Writing to ' + item[u'localFile'] + u'...'
                with open(item[u'localFile'], 'wb') as f:
                    resp = s.get(item[u'remoteFile'], stream=True, timeout=30)
                    resp.raise_for_status()
                    print 'File size: ' + str(len(resp.content))
                    for chunk in tqdm(resp.iter_content()):
                        f.write(chunk)
                if bid in playlist and fid not in playlist[bid]:
                    playlist[bid][fid] = item
                elif bid not in playlist:
                    playlist[bid] = {fid: item}
                with open(os.path.join('data', 'list.json'), 'w') as f:
                    json.dump(playlist, f, ensure_ascii=False)
    # Convert
    for bid in playlist:
        for fid in playlist[bid]:
            item = playlist[bid][fid]
            if u'convertedFile' in item:
                continue
            if u'type' not in item:
                item[u'type'] = item[u'localFile'].split(u'.')[-1]
            if item[u'type'] == u'mp3':
                f = eyed3.load(item[u'localFile'])
                time = f.info.time_secs
                print item[u'localFile'] + ': ' + str(time) + 's'
                pass
                item[u'convertedFile'] = item[u'localFile'].split(u'.')[0] + u'.mp4'
                ff = ffmpy.FFmpeg(
                    global_options='-y',
                    inputs={
                        item[u'localFile']: '-thread_queue_size 96',
                        item[u'localThumbnail']: '-loop 1 -t ' + str(time) + ' -r 10 -f image2'
                    },
                    outputs={
                        item[u'convertedFile']: '-c:v libx264 -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -crf 10 '
                                                '-r 10 -pix_fmt yuv420p'
                    }
                )
                print ff.cmd
                # Run
                ff.run()
            elif item[u'type'] == u'mp4':
                item[u'convertedFile'] = item[u'localFile']
            else:
                print u'Un recognized file type: ' + item[u'localFile']
                continue
            with open(os.path.join('data', 'list.json'), 'w') as f:
                json.dump(playlist, f, ensure_ascii=False)
    # Upload
    for bid in playlist:
        for fid in playlist[bid]:
            item = playlist[bid][fid]
            if u'uploaded' not in item:
                item[u'uploaded'] = u'False'
            if item[u'uploaded'] == u'False':
                pass
