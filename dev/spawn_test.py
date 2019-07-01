import os
import csv
import argparse
import requests
import urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MIGRID_URL = 'http://migrid.test'
OID_MIGRID_URL = 'https://oid.migrid.test'
JHUB_URL = 'http://127.0.0.1'

IMAGE_NAME = 'nielsbohr/slurm-notebook:edge'

parser = argparse.ArgumentParser()
parser.add_argument('--users', dest='users', default='',
                    help='a path to a csv file with users')
parser.add_argument('--global-pw', dest='global_pw', default='Passw0rd123',
                    help='Overwride default password for users')


def failed_on_url(URL, *args):
    print("Failed to process URL {} - msg: {}".format(URL, args))
    exit(1)


def main(args):
    # Spawn a server for each user
    users = []
    if args.users and isinstance(args.users, str) and os.path.exists(args.users):
        with open(args.users, 'r') as csv_file:
            header_values = [value.strip('\n').strip('#').strip(' ')
                             for value in csv_file.readline().split(';')]
            reader = csv.reader(csv_file, delimiter=';')
            for row in reader:
                user = {}
                for i, v in enumerate(row):
                    user[header_values[i]] = v
                users.append(user)

    for user in users:
        print("Spawn user {}".format(user.get('username', '')))
        if args.global_pw:
            user['password'] = args.global_pw
        with requests.session() as session:
            session.verify = False
            # Login to migrid
            result = session.get(MIGRID_URL)
            if result.status_code != 200:
                failed_on_url(MIGRID_URL)

            get_oid_ref = session.get(OID_MIGRID_URL + "/wsgi-bin/fileman.py")
            if get_oid_ref.status_code != 200:
                failed_on_url(OID_MIGRID_URL + "/openid")

            oid_ref = session.post(OID_MIGRID_URL + "/openid/allow",
                                   data={"identifier": "{}".format(
                                       user.get('email', '')),
                                       "password": "{}".format(
                                       user.get('password', '')),
                                       "remember": "yes",
                                       "yes": "yes"},
                                   headers={'Referer': get_oid_ref.url})
            if oid_ref.status_code != 200:
                failed_on_url(OID_MIGRID_URL + "/openid/allow",
                              "status code {}".format(oid_ref.status_code))

            service_modi = OID_MIGRID_URL + "/wsgi-bin/" \
                "reqjupyterservice.py?service=modi"
            get_jupyter_page = session.get(service_modi)
            if get_jupyter_page.status_code != 200:
                failed_on_url(service_modi)

            home_url = OID_MIGRID_URL + "/modi/hub/home"
            home_page = session.get(home_url)
            if home_page.status_code != 200:
                failed_on_url(home_url, "status code {}"
                              .format(home_page.status_code))

            # Parse DOM
            soup = BeautifulSoup(home_page.content, 'html.parser')
            stop = soup.find(id='stop')
            start = soup.find(id='start')

            if stop:
                # Get ID
                if hasattr(start, 'attrs') and 'href' in start.attrs:
                    user = start.attrs['href'].replace('/modi/user/', '').rstrip('/')
                    stop_url = OID_MIGRID_URL + '/modi/hub/api/'\
                        'users/{user}/server'.format(user=user)
                    stop_resp = session.delete(
                        stop_url,
                        headers={'Referer': OID_MIGRID_URL + '/modi/hub/home'}
                    )
                    if stop_resp.status_code != 204:
                        failed_on_url(stop_url, "status code {}"
                                      .format(stop_resp.status_code))
            if start:
                print('Starting Server')
                spawn_url = OID_MIGRID_URL + "/modi/hub/spawn"
                spawn_jupyter_page = session.get(spawn_url)
                if spawn_jupyter_page.status_code != 200:
                    failed_on_url(spawn_url, "status code {}"
                                  .format(spawn_jupyter_page.status_code))
                print("Spawned Server")


if __name__ == "__main__":
    main(parser.parse_args())
