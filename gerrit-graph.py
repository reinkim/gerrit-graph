#!/usr/bin/env python
# vim: fileencoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#
# Copyright 2013 Jinuk Kim, rein01@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


__author__ = 'rein01@gmail.com'
__version__ = '0.0.1'


import datetime
import json

import requests


def retrieve_stats(host, project, day_since, auth=None, n=500):
    if host[-1] == '/':
        host = host[:-1]

    # host/a/changes/?q=is:merged+...(resume)?n=500
    if auth:
        url = '%s/a/changes/?q=is:merged+project:%s{}&n=%d'
        httpauth = requests.auth.HTTPDigestAuth(*auth)
    else:
        url = '%s/changes/?q=is:merged+project:%s{}&n=%d'
        httpauth = None
    url = url % (host, project, n)

    headers = {'Accept': 'application/json',
               'Accept-Encoding': 'gzip'}

    stats = {}
    resume_key = None
    while True:
        if resume_key:
            resume = '+resume_sortkey:' + resume_key
        else:
            resume = ''
        print 'Get', url.format('')
        res = requests.get(url.format(resume),
                           auth=httpauth,
                           headers=headers)
        changes = json.loads(res.text[res.text.find('\n'):])
        print '    got {}'.format(len(changes))
        for cs in changes:
            _update_stats(stats, cs)

        if '_more_changes' in changes[-1] and changes[-1]['_more_changes']:
            first_day = _parse_datetime(changes[-1]['updated'])
            if first_day.date() < day_since:
                break
            resume_key = changes[-1]['_sortkey']
        else:
            break
    return stats


def _update_stats(stats, cs):
    begin = _parse_datetime(cs['created'])
    end = _parse_datetime(cs['updated'])
    if begin.date() == end.date():
        delta = (end - begin).seconds
        _add_stat(stats, begin.date(), delta)
    else:
        _add_stat(stats, begin.date(), _remaining_seconds(begin))
        current = begin.date()
        for i in xrange((end.date() - begin.date()).days - 1):
            _add_stat(stats, current, 86400)
            current += datetime.timedelta(days=1)
        _add_stat(stats, end.date(), 86400 - _remaining_seconds(end))


def _parse_datetime(dt_str):
    dt_str = dt_str.split('.', 1)[0]
    return datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')


def _add_stat(stats, date, delta):
    if date not in stats:
        stats[date] = delta
    else:
        stats[date] += delta


def _remaining_seconds(dt):
    zero = datetime.datetime(dt.year, dt.month, dt.day, 0, 0, 0)
    return (dt - zero).seconds


AXIS_THRESHOLDS = [(5, 1), (10, 2),
                  (20, 4), (25, 5), (30, 6),
                  (40, 4), (50, 5), (60, 6),
                  (80, 4), (100, 5), (120, 6),
                  (160, 4), (200, 5), (240, 6),
                  (250, 5), (300, 6),
                  (400, 4), (500, 5), (600, 6),
                  (800, 4), (1000, 5), (1200, 6),
                  (1600, 4), (2000, 5), (2400, 6),
                  (2500, 5), (3000, 6),
                  (4000, 4), (5000, 5), (6000, 6)]


def _find_axis_max(v):
    for val in AXIS_THRESHOLDS:
        if val[0] >= v:
            return val


def print_graph(output, stats, firstDay, lastDay):
    def _get_data(d):
        return stats.get(d, 0) / 86400.0

    HEIGHT = 120
    BAR = 3
    max_height, div = _find_axis_max(max(stats.values()) / 86400.0)
    max_height *= 1.0

    margin = 10
    days = (lastDay - firstDay).days + 1
    width = 20 + margin * 2 + BAR * days - 1
    height = margin + 12 + HEIGHT

    # svg boilerplate
    print >> output, '<?xml version="1.0" standalone="no"?>'
    print >> output, '<svg xmlns="http://www.w3.org/2000/svg"',
    print >> output, 'width="{}" height="{}">'.format(width, height)
    print >> output, '<!-- {} ~ {} -->'.format(firstDay, lastDay)
    print >> output, '<!-- max: {}, {} -->'.format(max(stats.values())/86400.0,
                                                   max_height)

    # print axis & labels
    label = ('<text dx="10" dy="{0}" style="font-size: 9px; fill: #333">'
             '{1}</text>')
    hr = ('<line x1="%d" y1="{0}" x2="%d" y2="{0}" '
          'style="stroke-width: 1; stroke: black; stroke-opacity: 0.2;"/>'
          % (margin + 20, width - margin))
    for i in xrange(div):
        y = 10 + HEIGHT / div * i
        pos = (div - i) * int(max_height) / div
        print >> output, label.format(y + 3, pos)
        print >> output, hr.format(y)
    print >> output, label.format(13 + HEIGHT, 0)
    print >> output, hr.format(10 + HEIGHT)

    # print bars
    print >> output, ('<g transform="translate({}, {})">'
                      .format(20 + margin, margin))
    cell = (' <rect width="%d" height="{0}" x="{1}" y="{2}" '
            'style="fill: {3};">{4}</rect>' % (BAR - 1))
    date_str = ('<text dx="{0}" dy="%d" style="font-size: 8px; fill: #333">'
                '{1}/{2}</text>' % (HEIGHT + 10))
    cur = firstDay
    for i in xrange(days):
        x = i * BAR
        data = _get_data(cur)
        height = data / max_height * HEIGHT
        y = HEIGHT - height
        print >> output, cell.format(height, x, y, '#f95', data)

        if cur.day == 1 and lastDay - cur > datetime.timedelta(days=5):
            print >> output, date_str.format(x, cur.year, cur.month)
        cur += datetime.timedelta(days=1)
    print >> output, '</g></svg>'


HOST = 'https://android-review.googlesource.com'
PROJECT = 'platform/sdk'

day_since = datetime.date.today() - datetime.timedelta(days=366)
stats = retrieve_stats(HOST, PROJECT, day_since)

minDay = day_since
maxDay = max(stats.keys())
with open('gerrit-stat-{}.svg'.format(PROJECT.replace('/', '_')), 'w+') as out:
    print_graph(out, stats, minDay, maxDay)
