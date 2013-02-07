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


import colorsys
import datetime
import json
import sys

import gflags
import requests


FLAGS = gflags.FLAGS


def retrieve_stats(stats, host, project, day_since, auth=None):
    if host[-1] == '/':
        host = host[:-1]
    httpauth = None
    if auth:
        httpauth = requests.auth.HTTPDigestAuth(*auth)

    _retrieve_stats(stats, host, project, day_since, True, auth=httpauth)
    _retrieve_stats(stats, host, project, day_since, False, auth=httpauth)
    return stats


def _retrieve_stats(stats, host, project, day_since, merged, auth=None, n=500):
    if '@' in project:
        project_str = 'project:{}+branch:{}'.format(*project.split('@'))
    else:
        project_str = 'project:{}'.format(project)

    status = 'is:merged' if merged else 'is:open'
    # host/a/changes/?q=is:merged+...(resume)?n=500
    if auth:
        url = '%s/a/changes/?q=%s+%s{}&n=%d'
    else:
        url = '%s/changes/?q=%s+%s{}&n=%d'
    url = url % (host, status, project_str, n)

    headers = {'Accept': 'application/json',
               'Accept-Encoding': 'gzip'}

    if merged:
        _update = _update_stats
    else:
        _update = _update_open_stats(datetime.datetime.now())

    resumeKey = None
    while True:
        if resumeKey:
            resume = '+resume_sortkey:' + resumeKey
        else:
            resume = ''
        res = requests.get(url.format(resume), auth=auth, headers=headers,
                           verify=FLAGS.safe)
        changes = json.loads(res.text[res.text.find('\n'):])
        if not changes:
            break
        for cs in changes:
            _update(stats, cs)

        if '_more_changes' in changes[-1] and changes[-1]['_more_changes']:
            firstDay = _parse_datetime(changes[-1]['updated'])
            if firstDay.date() < day_since:
                break
            resumeKey = changes[-1]['_sortkey']
        else:
            break


def _update_stats(stats, cs):
    begin = _parse_datetime(cs['created'])
    end = _parse_datetime(cs['updated'])
    _do_update_stats(stats, begin, end)


def _update_open_stats(now):
    def __update_open_stats(stats, cs):
        begin = _parse_datetime(cs['created'])
        _do_update_stats(stats, begin, now)
    return __update_open_stats


def _do_update_stats(stats, begin, end):
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
    c1 = colorsys.rgb_to_hls(0.1176, 0.4078, 0.1372)
    c2 = colorsys.rgb_to_hls(0.8392, 0.9019, 0.5215)
    c1 = colorsys.rgb_to_hls(0.9, 0.0, 0.0)
    c2 = colorsys.rgb_to_hls(0.2, 0.9, 0.0)

    def _get_color(v):
        p = v / max_height
        q = 1.0 - p
        c = (c1[0] * p + c2[0] * q, c1[1] * p + c2[1] * q,
             c1[2] * p + c2[2] * q)
        c = colorsys.hls_to_rgb(*c)
        c = tuple(int(_c * 255) for _c in c)
        return '#%02x%02x%02x' % c

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
        print >> output, cell.format(height, x, y, _get_color(data), data)

        if cur.day == 1 and lastDay - cur > datetime.timedelta(days=5):
            print >> output, date_str.format(x, cur.year, cur.month)
        cur += datetime.timedelta(days=1)
    print >> output, '</g></svg>'


gflags.DEFINE_string('host', None, 'gerrit server')
gflags.DEFINE_string('since', None, 'generate stats from this day')
gflags.DEFINE_string('out', None, 'output file to save graph')
gflags.DEFINE_string('auth', None, 'user:password')
gflags.DEFINE_boolean('safe', True, 'verify ssl certificate')

gflags.MarkFlagAsRequired('host')
gflags.MarkFlagAsRequired('out')


def main(argv):
    try:
        argv = FLAGS(argv)  # parse flags
    except gflags.FlagsError, e:
        print '%s\nUsage: %s ARGS\n%s' % (e, sys.argv[0], FLAGS)
        sys.exit(1)

    if FLAGS.since:
        daySince = datetime.datetime.strptime(FLAGS.since, '%Y-%m-%d').date()
    else:
        daySince = datetime.date.today() - datetime.timedelta(days=366)

    if FLAGS.auth:
        user, passwd = FLAGS.auth.split(':')
        auth = (user, passwd)
    else:
        auth = None

    projects = set(argv[1:])
    if not projects:
        print 'Please specify projects (eg. platform/sdk, platform/sdk@master)'
        sys.exit(1)

    stats = {}
    for project in projects:
        retrieve_stats(stats, FLAGS.host, project, daySince, auth=auth)
        lastDay = max(stats.keys())

    with open(FLAGS.out, 'w+') as out:
        print_graph(out, stats, daySince, lastDay)


if __name__ == '__main__':
    main(sys.argv)
