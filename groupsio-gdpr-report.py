#!/usr/local/bin/python3

# Copyright Brian Warner
#
# SPDX-License-Identifier: MIT
#
# Latest version and configuration instructions at:
#     https://github.com/brianwarner/groupsio-gdpr-reports

import os
import sys
import requests
import json
import re
from fpdf import FPDF
from datetime import datetime
import html
import getpass

from pprint import pprint

user = input('\nGroups.io admin username: ').strip()
password = getpass.getpass(prompt='Groups.io admin password: ')

email_pattern = re.compile("[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

### Find out who we're searching for ###

search_email_raw = email_pattern.findall(input('\nSearch for email: ').lower().strip())

if not search_email_raw:
    print('This does not appear to be a valid email')
    sys.exit()

search_email = search_email_raw[0]

search_user_id = 0

### Groups.io: Get the relevant subgroups ###

# Authenticate and get the cookie

session = requests.Session()
login = session.post(
        'https://groups.io/api/v1/login',
        data={'email':user,'password':password}).json()
cookie = session.cookies

csrf = login['user']['csrf_token']

### Find out which main groups the admin is a member of ###

more_groups = True
next_page_token_groups = 0
monitored_groups = dict()
found_accounts = list()
found_activity = dict()

groupsio_subgroups = dict()
groupsio_maingroups = dict()

print('\nSearching Groups.io for activity by %s' % search_email)

while more_groups:

    groups_page = session.post(
            'https://groups.io/api/v1/getsubs?limit=100&sort_field=group&page_token=%s' %
            (next_page_token_groups),
            cookies=cookie).json()

    if groups_page['object'] == 'error':
        print('Something went wrong: %s' % groups_page['type'])
        sys.exit()

    if groups_page and 'data' in groups_page:
        for group in groups_page['data']:
            if (not group['group_name'] == 'beta' and
                    not group['group_name'].find('+') > 0):

                found_activity[group['group_name']] = dict()

                group_data = session.post(
                        'https://groups.io/api/v1/getgroup?group_name=%s' %
                        (group['group_name']),
                        cookies=cookie).json()

                # Get some info about the group

                monitored_groups[group['group_name']] = {
                        'title': group_data['title'][:-11],
                        'domain': group_data['org_domain']}

                # Report which group we're checking

                print('\n * %s (%s)' %
                    (monitored_groups[group['group_name']]['title'],
                    monitored_groups[group['group_name']]['domain']))

                # Find out if the user is a member of the group

                search_group = session.post(
                        'https://groups.io/api/v1/searchmembers?group_name=%s&q=%s' %
                        (group['group_name'],search_email.replace('+','%2B')),
                        cookies=cookie).json()

                # If user is not a member, move to the next group

                if search_group['total_count']:
                    found_accounts.append(group['group_name'])

                    print ('  - %s is registered for this group, looking for relevant activity' %
                        search_email)

                else:
                    print ('  - %s is not a member of %s, skipping' %
                        (search_email,monitored_groups[group['group_name']]['title']))
                    continue

                search_user_id = search_group['data'][0]['user_id']

                # Check if the user has any activity on the main list

                print ('  - Checking main group')

                more_main_archives = True
                next_page_token_main_archives = 0

                while more_main_archives:

                    search_archives = session.post(
                            'https://groups.io/api/v1/searcharchives?group_name=%s&q=posterid:%s&limit=100&page_token=%s' %
                            (group['group_name'].replace('+','%2B'), search_user_id, next_page_token_main_archives),
                            cookies = cookie).json()

                    if search_archives['object'] == 'error':
                        print('Something went wrong: %s' % search_archives['type'])
                        sys.exit()

                    if search_archives['data']:
                        for message in search_archives['data']:
                            found_activity[group['group_name']]['main'] = {
                                'date': message['created'],
                                'subject': message['subject'],
                                'summary': message['summary']}

                    next_page_token_main_archives = search_archives['next_page_token']

                    if next_page_token_main_archives == 0:
                        more_main_archives = False

                # Get the subgroups of the current group

                more_subgroups = True
                next_page_token_subgroups = 0

                while more_subgroups:

                    subgroups = session.post(
                        'https://groups.io/api/v1/getsubgroups?group_name=%s&limit=100&page_token=%s' %
                        (group['group_name'],next_page_token_subgroups),
                        cookies=cookie).json()

                    if subgroups['object'] == 'error':
                        print('Something went wrong: %s' % subgroups['type'])
                        sys.exit()

                    if not subgroups['data']:
                        print('  - No subgroups defined, moving to next group.')
                        continue

                    print('  - Checking subgroups:')

                    for subgroup in subgroups['data']:

                        print('    > Checking %s' %
                            subgroup['name'][len(group['group_name'])+1:])

                        more_subgroup_archives = True
                        next_page_token_subgroup_archives = 0

                        while more_subgroup_archives:

                            search_subgroup_archives = session.post(
                                    'https://groups.io/api/v1/searcharchives?group_name=%s&q=posterid:%s&sort_dir=asc&sort_field=updated&limit=100&page_token=%s' %
                                    (subgroup['name'].replace('+','%2B'), search_user_id, next_page_token_subgroup_archives),
                                    cookies = cookie).json()

                            if search_subgroup_archives['object'] == 'error':
                                print('Something went wrong: %s' % search_subgroup_archives['type'])
                                sys.exit()

                            found_activity[group['group_name']][subgroup['name']] = list()

                            if search_subgroup_archives['data']:

                                for message in search_subgroup_archives['data']:

                                    found_activity[group['group_name']][subgroup['name']].append({
                                        'date': message['created'],
                                        'subject': message['subject'],
                                        'summary': message['summary']})

                            next_page_token_subgroup_archives = search_subgroup_archives['next_page_token']

                            if next_page_token_subgroup_archives == 0:
                                more_subgroup_archives = False

                    next_page_token_subgroups = subgroups['next_page_token']

                    if next_page_token_subgroups == 0:
                        more_subgroups = False

    next_page_token_groups = groups_page['next_page_token']

    if next_page_token_groups == 0:
        more_groups = False

# Bail out if the admin isn't a member of any groups

if not monitored_groups:
    print('%s is not a member of any Groups.io groups, and cannot search for activity' % user)
    sys.exit()

### Print out a summary """

print('\n------- Summary -------\n\nThe following groups were scanned:\n')

for name,description in monitored_groups.items():

    print(' * %s (%s)' % (description['title'],description['domain']))

if found_accounts:
    print('\nAccounts were found in the following groups:\n')

    for name in found_accounts:

        print(' * %s (%s)' % (monitored_groups[name]['title'],monitored_groups[name]['domain']))

else:
    print('No accounts were found. User is not registered in Groups.io.')

if found_activity:
    print('\nActivity was found in the following groups:\n')

    for name,activity in found_activity.items():

        if activity:
            print(' * %s (%s)' % (monitored_groups[name]['title'],monitored_groups[name]['domain']))

else:
    print('No activity found for user in Groups.io.')

### Generate a PDF report ###

generated_date = datetime.now().strftime("%B %d, %Y")
reportfile = 'Groups.io GDPR search report - %s - %s.pdf' % (search_email,datetime.now().strftime("%Y-%m-%d"))

pdf = FPDF()

pdf.add_font("DejaVuSerif", style="", fname=os.path.join(os.path.dirname(__file__),'fonts','ttf','DejaVuSerif.ttf'), uni=True)
pdf.add_font("DejaVuSerif", style="B", fname=os.path.join(os.path.dirname(__file__),'fonts','ttf','DejaVuSerif-Bold.ttf'), uni=True)

pdf.add_page()

# Set the title

pdf.set_font('DejaVuSerif', 'B', 18)

pdf.cell(w=0, h=20, ln=1, txt='')

pdf.multi_cell(w=0, h=10, border=0, align='C', fill=0, txt='GDPR Request:\n%s' % search_email)

# Set the subtitle

pdf.cell(w=0, h=10, ln=1, txt='')

pdf.set_font('DejaVuSerif', 'B', 14)

pdf.multi_cell(w=0, h=9, border=0, align='C', fill=0, txt='Mailing list activity report:\n%s' % generated_date)

pdf.cell(w=0, h=15, ln=1, txt='')

# Create the abstract

pdf.set_font('DejaVuSerif', '', 12)

pdf.multi_cell(w=0, h=5, align='L', txt='The Linux Foundation has received a GDPR request regarding "%s".' % search_email)

pdf.cell(w=0, h=3, ln=1, txt='')

pdf.multi_cell(w=0, h=5, align='L', txt='We have searched for accounts and activity in the following Groups.io groups:')

pdf.cell(w=0, h=3, ln=1, txt='')

for name,description in monitored_groups.items():

    pdf.cell(w=0, h=6, align='L', ln=1, txt= '  » %s (%s)' %
        (description['title'],description['domain']))

pdf.cell(w=0, h=3, ln=1, txt='')

pdf.set_font('DejaVuSerif', 'B', 14)

# Summarize the accounts and activities

pdf.cell(w=0, h=9, txt='Summary', border=0, ln=1, align='C', fill=0)

pdf.cell(w=0, h=5, ln=1, txt='')

pdf.set_font('DejaVuSerif', '', 12)

# Report found accounts

if found_accounts:

    pdf.multi_cell(w=0, h=5, align='L', txt = 'Accounts for %s were found in the following groups:' % search_email)

    pdf.cell(w=0, h=3, ln=1, txt='')

    for name in found_accounts:

        summary = '  » %s (https://%s)' % (monitored_groups[name]['title'],monitored_groups[name]['domain'])

        pdf.cell(w=0, h=6, align='L', ln=1, txt=summary)

    pdf.cell(w=0, h=6, ln=1, txt='')

else:

    pdf.multi_cell(w=0, h=5, align='L', txt='%s is not subscribed to any Groups.io instances managed by The Linux Foundation.' % search_email)

# Report found activity

if found_activity:

    pdf.multi_cell(w=0, h=5, align='L', txt = 'Activity by %s was found in the following groups:' % search_email)

    pdf.cell(w=0, h=3, ln=1, txt='')

    for name,activity in found_activity.items():

        if activity:
            summary = '  » %s (https://%s)' % (monitored_groups[name]['title'],monitored_groups[name]['domain'])

            pdf.cell(w=0, h=6, align='L', ln=1, txt=summary)

    # Print a page with a report of each subgroup

    for groupname,subgroups in found_activity.items():

        if not subgroups:
            continue

        pdf.add_page()

        # Add a page title

        pdf.cell(w=0, h=10, ln=1, txt='')

        pdf.set_font('DejaVuSerif', 'B', 16)

        pdf.multi_cell(w=0, h=9, border=0, align='C', fill=0, txt='%s\nhttps://%s' %
            (monitored_groups[groupname]['title'],monitored_groups[groupname]['domain']))

        pdf.cell(w=0, h=15, ln=1, txt='')

        # Print activity from subgroups

        for subgroup,archives in subgroups.items():

            pdf.set_font('DejaVuSerif', 'B', 16)

            pdf.multi_cell(w=0, h=10, align='L', txt='Subgroup:  "%s"' %
                subgroup[len(groupname)+1:])

            pdf.cell(w=0, h=5, ln=1, txt='')

            if not archives:

                pdf.set_font('DejaVuSerif', '', 12)

                pdf.multi_cell(w=0, h=5, align='L', txt= '%s only received messages. No activity found.' % search_email)

                pdf.cell(w=0, h=10, ln=1, txt='')

                continue

            for entry in archives:

                pdf.set_font('DejaVuSerif', 'B', 12)

                pdf.multi_cell(w=0, h=6, align='L', txt='Subject:')

                pdf.set_font('DejaVuSerif', '', 12)

                pdf.multi_cell(w=0, h=6, align='L', txt=html.unescape(entry['subject']))

                pdf.cell(w=0, h=3, ln=1, txt='')

                pdf.set_font('DejaVuSerif', 'B', 12)

                pdf.multi_cell(w=0, h=6, align='L', txt='Date:')

                pdf.set_font('DejaVuSerif', '', 12)

                pdf.multi_cell(w=0, h=6, align='L', txt=entry['date'])

                pdf.cell(w=0, h=3, ln=1, txt='')

                pdf.set_font('DejaVuSerif', 'B', 12)

                pdf.multi_cell(w=0, h=6, align='L', txt='Excerpt:')

                pdf.set_font('DejaVuSerif', '', 12)

                ellipses = ''
                if len(html.unescape(entry['summary'])) >= 199:
                    ellipses = '...'

                pdf.multi_cell(w=0, h=6, align='L', txt=('%s%s' %
                    (html.unescape(entry['summary']),ellipses)))

                pdf.cell(w=0, h=10, ln=1, txt='')

else:
    pdf.multi_cell(w=0, h=5, align='L', txt= '%s only received messages. No activity found.' % search_email)

pdf.cell(w=0, h=3, ln=1, txt='')

pdf.output(reportfile, 'F')

print('\nReport created: %s\n' % reportfile)
