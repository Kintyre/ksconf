"""

https://dev.splunk.com/enterprise/reference/splunkbase/sbreleaseapiref/


Lookup based on folder name:

https://apps.splunk.com/apps/id/python_upgrade_readiness_app

Download URL:

https://splunkbase.splunk.com/app/4383/release/0.9.0/download/?origin=asc&lead=false





From "Analysis Of SplunkBase Apps for Splunk":  (https://splunkbase.splunk.com/app/2919)

  # Base URL to download list of apps
  base_url = "https://splunkbase.splunk.com/api/v1/app/?order=latest&limit=" + \
      str(limit) + "&include=support,created_by,categories,icon,screenshots,rating,releases,documentation,releases.content,releases.splunk_compatibility,releases.cim_compatibility,releases.install_method_single,releases.install_method_distributed,release,release.content,release.cim_compatibility,release.install_method_single,release.install_method_distributed,release.splunk_compatibility&instance_type=cloud" + "&offset="




"""


import json
import os
import re
import time

import requests
from requests.auth import HTTPBasicAuth

APP_ID = 4383
versions = ["7.2", "7.3", "8.0", "8.1"]


class SplunkBaseConnection:
    api_url = "https://splunkbase.splunk.com"

    def __init__(self, username=None, password=None):
        self._auth = (username, password)

    def request(self, method, rel_url, *args, **kwargs):
        response = requests.request(method, "{}/{}".format(self.api_url, rel_url),
                                    auth=HTTPBasicAuth(*self._auth), *args, **kwargs)
        return response

    def get_app(self, app_id):
        return SplunkBaseApp(self, app_id)


class SplunkBaseApp:

    def __init__(self, connection, app_id):
        # type: (SplunkBaseConnection, int) -> None
        self.conn = connection
        self.app_id = app_id

    def upload_release(self, tarball, splunk_versions, cim_versions=[], visibility=False):
        """
        Returns release id
        """
        payload = {
            "filename=": os.path.basename(tarball),
            "splunk_versions": ",".join(splunk_versions),
            "visibility": "true" if visibility else "false",
        }
        if cim_versions:
            payload["cim_versions"] = ",".join(cim_versions)

        with open(tarball, "rb") as tb:
            response = self.conn.request(
                "post", "/api/v1/app/{}/new_release/".format(self.app_id),
                files={"files[]": tb},
                data=payload)
            data = response.text
            try:
                data = json.loads(data)
            except ValueError:
                print("Non json:  ", data)
                raise
            print("Response:  {}".format(data))
            return data["id"]

    def validate_upload(self, package_id):
        while True:
            response = self.con.request("get", "/api/v1/package/{}/".format(package_id))
            data = response.json()
            print(data)

            if "result" in data:
                return
            time.sleep(10)

            # {'result': 'pass', 'message': {'release_file': 19879, 'release_name': '0.8.4rc1', 'app_id': 'ksconf', 'icon': 3540}}
            # {'result': 'pass', 'message': {'release_file': 19892, 'release_name': '0.8.4', 'app_id': 'ksconf', 'icon': 3540}}

            # 19879
            # https://splunkbase.splunk.com/app/4383/edit/#/hosting/19879
            # https://splunkbase.splunk.com/app/{APP_ID}/edit/#/hosting/{RELEASE_FILE}

    def get_release(self, release_id):
        # Yes "v0.1" -- weird, but it's what works.  ::facepalm::
        data = self.conn.request("get", "/api/v0.1/app/{}/release/{}/".format(self.app_id, release_id)).json()
        print(data)
        return data

    def put_release_notes(self, release_id, release_notes):
        """ Get the existing release details and only overwrite the 'release_notes' attribute. """
        url = "/api/v0.1/app/{}/release/{}/".format(self.app_id, release_id)
        # Technically this call can be unauthenticated
        data = self.conn.request("get", url).json()
        data["release_notes"] = release_notes
        # Using 'PUT' rather than POST... (confirm)
        response = self.conn.request("put", url, data=json.dumps(data),
                                     headers={"Content-Type": "application/json;charset=UTF-8"},)
        response.raise_for_status()
        data = response.json()
        return data


p = "/Users/lalleman/Downloads/ksconf-app_for_splunk-0.8.4.tgz"


change_log = "docs/source/changelog.rst"


"""

NEW APPROACH:


re.split(r"[\r\n](Ksconf|Release) v(?P<version>[0-9.rcbeta]+)", data)



OLD APPROACH:



def read_sections(stream):
    content = []
    header = None
    for line in stream:
        if re.match(r"^[=-_~]{4,100}$", line):
            if content:
                yield (header, content)
                header = None
                content = []
        else:
            header = line
            content.append(line)
    if content:
        yield header, content


def get_sections():
    with open(change_log) as changelog:
        for header, content in read_sections(changelog):
            mo = re.search(r"^(Ksconf|Release) v(?P<version>[0-9.rcbeta]+)", header)
            if mo:
                print(mo.groupdict())
                d = {}
                d.update(mo.groupdict())
                d["content"] = "".join(content)
                yield d
"""

if __name__ == '__main__':

    splunkbase = SplunkBaseConnection("USERNAME", "PASSWORD")
    app = splunkbase.get_app(APP_ID)

    # upload_id = upload_new_releases(APP_ID, p, versions, visibility=False)
    # validate_upload(upload_id)
    upload_id = app.upload_release(p, versions, visibility=False)
    app.validate_upload(upload_id)

    # d = get_release(4383, 19892)

    for d in get_sections():
        if d["version"] == "0.8.4":
            content = d["content"]

    print("Changelog found:::")

    print(content)

    # data = put_release_notes(4383, 19892, content)
    app.put_release_notes(19892, content))
    print(data)


"""

NO Clue what this one does, but it happens RIGHT before the release notes push:

https://splunkbase.splunk.com/api/v1/user/Kintyre/?fields=id

Response:  {"id":281827}






{
	"id": 19879,
	"app": 4383,
	"name": "0.8.4rc1",
	"release_notes": "Release notes",
	"CIM_versions": [],
	"splunk_versions": [
		"8.1",
		"8.0",
		"7.3",
		"7.2"
	],
	"public": false,
	"public_ever_true": false,
	"created_datetime": "2021-03-23T04:21:29.432154Z",
	"published_datetime": "2021-03-23T04:21:29.432189Z",
	"size": 648897,
	"filename": "ksconf_084rc1.tgz",
	"platform": "independent",
	"is_bundle": true,
	"has_ui": false,
	"approved": false,
	"appinspect_status": false,
	"install_method_single": "unknown",
	"install_method_distributed": "unknown",
	"requires_cloud_vetting": false,
	"appinspect_request_id": null,
	"cloud_vetting_request_id": null,
	"python3_acceptance": true,
	"python3_acceptance_datetime": "2021-03-23T04:28:48.885Z",
	"python3_acceptance_user": 281827,
	"fedramp_validation": "no",
	"cloud_compatible": false
}



Response:


{"id":19879,"app":4383,"name":"0.8.4rc1","release_notes":"Release notes","CIM_versions":[],"splunk_versions":["8.1","8.0","7.3","7.2"],"public":false,"public_ever_true":false,"created_datetime":"2021-03-23T04:21:29.432154Z","published_datetime":"2021-03-23T04:21:29.432189Z","size":648897,"filename":"ksconf_084rc1.tgz","platform":"independent","is_bundle":true,"has_ui":false,
    "approved":false,"appinspect_status":false,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":null,"cloud_vetting_request_id":null,"python3_acceptance":true,"python3_acceptance_datetime":"2021-03-23T04:28:48.885000Z","python3_acceptance_user":281827,"fedramp_validation":"no","cloud_compatible":false}

"""


"""

SET THE DEFAULT APP:





https://splunkbase.splunk.com/api/v0.1/app/4383/


Request URL: https://splunkbase.splunk.com/api/v0.1/app/4383/
Request Method: PUT
Status Code: 200 OK
Remote Address: 44.228.247.153:443
Referrer Policy: strict-origin-when-cross-origin
Allow: GET, PUT, PATCH, DELETE, HEAD, OPTIONS
Connection: keep-alive
Content-Length: 22674
Content-Type: application/json
Date: Wed, 24 Mar 2021 01:59:36 GMT
Server: Apache
Vary: Cookie
Accept: application/json, text/plain, */*
Accept-Encoding: gzip, deflate, br
Accept-Language: en-US,en;q=0.9
Cache-Control: no-cache
Connection: keep-alive
Content-Length: 21864
Content-Type: application/json;charset=UTF-8
Cookie: _ga=GA1.2.1363921037.1524673772; ....
DNT: 1
Host: splunkbase.splunk.com
Origin: https://splunkbase.splunk.com
Pragma: no-cache
Referer: https://splunkbase.splunk.com/app/4383/edit/
sec-ch-ua: "Google Chrome";v="89", "Chromium";v="89", ";Not A Brand";v="99"
sec-ch-ua-mobile: ?0
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: same-origin
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36
X-CSRFToken: ....




Original modified by chrome inspect:


{"id":4383,"name":"KSCONF","categories":[5],"description":"Git and Splunk don't always fit together perfectly.  Introducing KSCONF, a tool written to alleviate painful tasks associated with managing Splunk apps in a git repository.  This open source tool supports many functions to help both admins and developers manage Splunk content in git in a simple way without getting stuck in the details.\n\nhttps://github.com/Kintyre/ksconf","created_by":{"id":281827,"username":"Kintyre","email":"splunkbase@kintyre.co"},"created_datetime":"2019-02-07T05:19:15.049156Z","published_datetime":"2019-02-07T18:20:11.949680Z","releases":[{"id":19892,"app":4383,"name":"0.8.4","release_notes":"","CIM_versions":[],"splunk_versions":[30,31,25,24,21],"public":false,"public_ever_true":false,"created_datetime":"2021-03-24T00:32:28.701412Z","published_datetime":"2021-03-24T00:32:28.701446Z","size":648848,"filename":"ksconf_084.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":false,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":null,"cloud_vetting_request_id":null,"python3_acceptance":true,"python3_acceptance_datetime":"2018-11-09T23:34:52.200916Z","python3_acceptance_user":8438,"fedramp_validation":"no","cloud_compatible":false},{"id":19879,"app":4383,"name":"0.8.4rc1","release_notes":"Release notes","CIM_versions":[],"splunk_versions":[31,25,24,21],"public":false,"public_ever_true":false,"created_datetime":"2021-03-23T04:21:29.432154Z","published_datetime":"2021-03-23T04:21:29.432189Z","size":648897,"filename":"ksconf_084rc1.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"1aa57d6d-b535-4c07-bd07-227cdc3a5901","cloud_vetting_request_id":"c0cbfaf3-362a-4fba-917b-c2e0a4e506db","python3_acceptance":true,"python3_acceptance_datetime":"2021-03-23T04:28:48.885000Z","python3_acceptance_user":281827,"fedramp_validation":"no","cloud_compatible":false},{"id":19853,"app":4383,"name":"0.8.3","release_notes":"* New command ksconf package is designed for both Splunk developers and admins.  This includes simple but helpful options to merge ‘local’ into ‘default’, set the an app version, set the top-level folder name (if it’s different on the file system), and so on.\n* New module ksconf.builder helps build Splunk apps using a pipeline; or when external Python libraries are bundled into an app\n* Legit layer support with built-in layer filtering capabilities is available in several commands.  Now you can easily have layers for both \"default\" and \"lookups\", for example.\n* Python 3! Head's up: We'll be dropping support for Python 2 in an upcoming release\n\nOfficial change log:  https://ksconf.readthedocs.io/en/latest/changelog.html#ksconf-0-8","CIM_versions":[],"splunk_versions":[31,25,24,21],"public":true,"public_ever_true":true,"created_datetime":"2021-03-21T02:03:41.974542Z","published_datetime":"2021-03-21T02:03:41.974612Z","size":645225,"filename":"ksconf_083.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"15c9db33-160c-44ed-ba81-aefd9e5b3036","cloud_vetting_request_id":"d0dfb0e6-0bdd-429b-b08f-1950688acd84","python3_acceptance":true,"python3_acceptance_datetime":"2021-03-22T15:14:12.420000Z","python3_acceptance_user":281827,"fedramp_validation":"no","cloud_compatible":false},{"id":19850,"app":4383,"name":"0.7.10","release_notes":"Empty stanza bug fix\n\n* Fixed bug where empty stanzas in the local file could result in stanza removal in default with ksconf promote.\n* Updated diff interface to improve handling of empty stanzas","CIM_versions":[],"splunk_versions":[30,31,25,24,21],"public":true,"public_ever_true":true,"created_datetime":"2021-03-19T22:29:13.684251Z","published_datetime":"2021-03-19T22:29:13.684286Z","size":554531,"filename":"ksconf_0710.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"aeaffc11-9f39-4609-bef9-e31565ec1532","cloud_vetting_request_id":"11c73796-4445-4ce1-b631-b92dfe9708a5","python3_acceptance":true,"python3_acceptance_datetime":"2021-03-19T22:29:50.891000Z","python3_acceptance_user":281827,"fedramp_validation":"no","cloud_compatible":false},{"id":17006,"app":4383,"name":"0.7.8","release_notes":"https://ksconf.readthedocs.io/en/latest/changelog.html#release-v0-7-8-2020-06-19","CIM_versions":[],"splunk_versions":[30,31,25,24,21,20,19,18],"public":true,"public_ever_true":true,"created_datetime":"2020-06-20T00:24:28.796543Z","published_datetime":"2020-06-20T00:24:28.796578Z","size":540080,"filename":"ksconf_078.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":false,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"8e5e4387-1be0-4037-b516-0191220bc560","cloud_vetting_request_id":"6497dd9e-e883-4174-a197-9fcf675823a5","python3_acceptance":true,"python3_acceptance_datetime":"2020-06-20T00:28:51.245000Z","python3_acceptance_user":8438,"fedramp_validation":"no","cloud_compatible":false},{"id":17004,"app":4383,"name":"0.7.7","release_notes":"","CIM_versions":[],"splunk_versions":[30,31,25,24,21,20,19,18],"public":true,"public_ever_true":true,"created_datetime":"2020-06-20T00:22:34.501141Z","published_datetime":"2020-06-20T00:22:34.501176Z","size":531057,"filename":"ksconf_077.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"b018e169-4a5e-416e-92ad-ae1bd1635a07","cloud_vetting_request_id":"f84cedc6-b70d-454b-8e4e-3055950c27d7","python3_acceptance":true,"python3_acceptance_datetime":"2020-06-20T00:23:02.901000Z","python3_acceptance_user":8438,"fedramp_validation":"no","cloud_compatible":false},{"id":14395,"app":4383,"name":"0.7.7rc5","release_notes":"Release Candidate","CIM_versions":[],"splunk_versions":[24,21,20,19,18],"public":false,"public_ever_true":true,"created_datetime":"2019-10-18T16:15:27.797465Z","published_datetime":"2019-10-18T16:15:27.797499Z","size":528708,"filename":"ksconf_077rc5.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"40fa0a0d-7809-4a3c-bda0-1de8ee667e57","cloud_vetting_request_id":"92d8d55f-ae86-4e1d-90d8-ea4c9d1efab0","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":13785,"app":4383,"name":"0.7.6","release_notes":"","CIM_versions":[],"splunk_versions":[24,21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-08-16T14:55:34.530575Z","published_datetime":"2019-08-16T14:55:34.530592Z","size":520292,"filename":"ksconf_076.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"429ab01d-0b78-46c3-8cd1-d795acf77947","cloud_vetting_request_id":"14624e32-4e23-49d5-b826-91403087b519","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":13472,"app":4383,"name":"0.7.5","release_notes":"","CIM_versions":[],"splunk_versions":[24,21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-07-03T20:59:39.414179Z","published_datetime":"2019-07-03T20:59:39.414196Z","size":517685,"filename":"ksconf_075.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"7d31b54d-4c17-4dd0-8d73-58198093b693","cloud_vetting_request_id":"ec9de1d4-3011-4b5d-8abb-be90b8a7acbb","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":13289,"app":4383,"name":"0.7.4","release_notes":"","CIM_versions":[],"splunk_versions":[24,21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-06-08T03:10:45.997841Z","published_datetime":"2019-06-08T03:10:45.997859Z","size":520353,"filename":"ksconf_074.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"46be62c1-63f4-45c7-8b23-4c54a9d24d99","cloud_vetting_request_id":"dc8a900c-7ed3-4bc1-b2a9-726301c19a65","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":13265,"app":4383,"name":"0.7.3","release_notes":"","CIM_versions":[],"splunk_versions":[24,21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-06-05T20:08:38.145134Z","published_datetime":"2019-06-05T20:08:38.145152Z","size":520666,"filename":"ksconf_073.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"1ae17d85-a2b0-4368-99ad-57e7f42b4e63","cloud_vetting_request_id":"0368788d-92fb-4603-a171-a9f537650ade","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":12648,"app":4383,"name":"0.7.2","release_notes":"","CIM_versions":[],"splunk_versions":[21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-03-22T17:52:03.936188Z","published_datetime":"2019-03-22T17:52:03.936206Z","size":539078,"filename":"ksconf_072.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"d7e3e64f-8080-4981-ac32-37933455eddf","cloud_vetting_request_id":"61c731c5-a08a-4a74-9c68-8d33c896d319","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             "id":12594,"app":4383,"name":"0.7.1","release_notes":"","CIM_versions":[],"splunk_versions":[21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-03-14T03:10:11.186627Z","published_datetime":"2019-03-14T03:10:11.186646Z","size":537957,"filename":"ksconf_071.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"0b3a6a98-1010-4a26-9130-f02d39be357b","cloud_vetting_request_id":"01bce7c2-4272-4758-bec7-33d2e150ee21","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":12477,"app":4383,"name":"0.7.0","release_notes":"This release fixes up packaging issues with python package folders that may caused issues after upgrades.  Unfortunately, this means everyone who had installed 0.6.x should uninstall and do a fresh install of 0.7.0.  Hopefully this issue is resolved and extra steps like this won't be required in the future.\n\nAs always, read the full change log here:\nhttps://ksconf.readthedocs.io/en/v0.7.0/changelog.html#release-v0-7-0-2019-02-27","CIM_versions":[],"splunk_versions":[21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-02-28T02:51:37.613788Z","published_datetime":"2019-02-28T02:51:37.613805Z","size":535787,"filename":"ksconf_070.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"2925ec27-a7f8-4545-95ba-6f3e0a7b3a7a","cloud_vetting_request_id":"ff363c9c-9084-41c3-a7a8-b8631778a53e","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":12471,"app":4383,"name":"0.7.0rc1","release_notes":"","CIM_versions":[],"splunk_versions":[],"public":false,"public_ever_true":false,"created_datetime":"2019-02-27T16:54:43.513971Z","published_datetime":"2019-02-27T16:54:43.513989Z","size":531948,"filename":"ksconf_070rc1.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"28379af1-9de5-4aa4-a874-dfba11cbd244","cloud_vetting_request_id":"0f4980a8-914f-4037-b556-e275810e5a2a","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":12417,"app":4383,"name":"0.6.3rc3","release_notes":"Pre-release 0.6.3 rc3","CIM_versions":[],"splunk_versions":[21,20,19,18,16,15,14,13,8,7],"public":false,"public_ever_true":true,"created_datetime":"2019-02-22T00:51:50.600067Z","published_datetime":"2019-02-22T00:51:50.600084Z","size":523067,"filename":"ksconf_063rc3.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"1e127732-0ef5-4ba8-8e2d-4aad7acc3afe","cloud_vetting_request_id":"864cb6e9-a4bf-4eb9-a247-4d6f2b8d1323","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":12264,"app":4383,"name":"0.6.2","release_notes":"https://ksconf.readthedocs.io/en/latest/changelog.html#release-v0-6-2-2019-02-09","CIM_versions":[],"splunk_versions":[21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-02-09T06:03:33.999915Z","published_datetime":"2019-02-09T06:03:33.999932Z","size":391401,"filename":"ksconf_062.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"9f6cea49-d078-451c-b013-d85a5954666a","cloud_vetting_request_id":"8888f017-b595-4592-ac30-31c602b2fdf8","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false},{"id":12245,"app":4383,"name":"0.6.1","release_notes":"","CIM_versions":[],"splunk_versions":[21,20,19,18,16,15,14,13,8,7],"public":true,"public_ever_true":true,"created_datetime":"2019-02-07T05:06:31.774524Z","published_datetime":"2019-02-07T05:06:31.774542Z","size":360202,"filename":"ksconf_061.tgz","platform":"independent","is_bundle":true,"has_ui":false,"approved":false,"appinspect_status":true,"install_method_single":"unknown","install_method_distributed":"unknown","requires_cloud_vetting":false,"appinspect_request_id":"a2f77bb5-db7c-41fb-b1fb-8246c72a1539","cloud_vetting_request_id":"c6f48670-9c10-4572-977e-41de133b8033","python3_acceptance":false,"python3_acceptance_datetime":null,"python3_acceptance_user":null,"fedramp_validation":"no","cloud_compatible":false}],"type":"app","support":"developer","contact_email":"lowell@kintyre.co","latest_release":"19892","access":"unrestricted","approved":true,"icon_url":"https://cdn.apps.splunk.com/media/public/icons/69b26e78-8c38-11eb-92f2-025a6208ee83.png","inquiry_url":"","inquiry_buttontext":"Contact Sales","price":"","documentation_source":"# What is KSCONF?\n\nKSCONF is a command-line tool that helps administrators and developers manage their Splunk environments by enhancing control of their configuration files.  The interface is modular so that each function (or subcommand) can be learned quickly and used independently.  While most users will probably only use a subset of the total capabilities of this tool, it’s reassuring to have a deep toolbox of power goodies ready to be unleashed at a moments notice.  Ksconf works with (and does not replace) your existing Splunk deployment mechanisms and version control tools.\n\nKSCONF is open source and an open development effort.  Check us out on [GitHub](https://github.com/Kintyre/ksconf#kintyres-splunk-configuration-tool)\n\nPronounced:   k·s·kȯnf\n\n## Design principles\n\n- *Ksconf is a toolbox.*  - Each tool has a specific purpose and function that works independently.  Borrowing from the Unix philosophy, each command should do one small thing well and be easily combined to handle higher-order tasks.\n- *When possible, be familiar.* - Various commands borrow from popular UNIX command line tools such as “grep” and “diff”.  The overall modular nature of the command is similar to the modular interface used by “git” and the “splunk” cli.\n- *Don’t impose workflow.* - Ksconf works with or without version control and independently of your deployment mechanisms.  (If you are looking to implement these things, ksconf is a great building block)\n- *Embrace automated testing.* - It’s impractical to check every scenarios between each release, but significant work has gone into unittesting the CLI to avoid breaks between releases.\n\n## Common uses for ksconf\n- Promote changes from “local” to “default”\n- Maintain multiple independent layers of configurations\n- Reduce duplicate settings in a local file\n- Upgrade apps stored in version control\n- Merge or separate configuration files\n- Push .conf stanzas to a REST endpoint (send custom configs to Splunk Cloud)\n\n## What's in the KSCONF App for Splunk?\n\nThis Splunk app comes bundled with a CLI tool that helps manage other Splunk apps.  While this is not a traditional use case for a Splunk app, it is a very quick and easy way to deploy ksconf.\n\nWhy did we make this a Splunk app?   Well, while ksconf is technically just a Python package that can be deployed in a variety of ways, we found that the logistics of getting it deployed can be quite difficult due to a packaging issues, legacy cruft, and OS limitations.  This approach avoids all that mess.\n\n\n# Getting Started\n\nFull documentation for ksconf and, therefore this app, is hosted at read-the-docs.  A full copy of the `ksconf` documentation is also included, just like how Splunk ships with a fully copy of the docs in the system/README folder.  (And all the air-gapped people rejoice! but sadly, no one could hear them.)\n\n\n## Docs\n\n  * [Official docs](https://ksconf.readthedocs.io/en/latest/) hosted via ReadTheDocs.io\n  * [Command line reference](https://ksconf.readthedocs.io/en/latest/cmd.html)\n\n## Need help?\n\n * [Ask questions](https://github.com/Kintyre/ksconf/issues/new?labels=question)\n * Chat about [#ksconf](https://slack.com/app_redirect?channel=CDVT14KUN) on the Splunk User group [Slack](https://splunk-usergroups.slack.com) channel\n\n## Get Involved\n\n * [Report bugs](https://github.com/Kintyre/ksconf/issues/new?template=bug.md)\n * Review [known bugs](https://github.com/Kintyre/ksconf/labels/bug)\n * [Request new features](https://github.com/Kintyre/ksconf/issues/new?template=feature-request.md&labels=enhancement)\n * [Contribute code](https://ksconf.readthedocs.io/en/latest/devel.html#contributing)\n\n## Roadmap\n\nAdditional Splunk UI feature are planned, but currently not implemented.\n\n * Dashboard to track all changes coordinated by `ksconf`\n * Configuration snapshot tracking\n * Custom SPL command to give visibility into the what exists in the `local` folder.  (The built-in `rest` command only shows you the final merged view of your settings; and sometimes you have to look deeper.)\n\n## Installation & Configuration\n\nSee the [Install an add-on](https://docs.splunk.com/Documentation/AddOns/released/Overview/Singleserverinstall) in Splunk's official documentation.  There is one manual step required to active the CLI portion of this app, if you choose to do so.  See the [Installation docs](https://ksconf.readthedocs.io/en/latest/install.html) for more details.\n\n## Support\n\nCommunity support is available on best-effort basis.  For information about commercial support, contact [Kintyre](mailto:hello@kintyre.co)\nIssues are tracked via [GitHub](https://github.com/Kintyre/ksconf/issues)\n\n## History\nSee the full [Change log](https://ksconf.readthedocs.io/en/latest/changelog.html)","screenshot_files":[],"docimage_files":[],"license_name":"Apache 2","license_url":"https://www.apache.org/licenses/LICENSE-2.0","appinspect_status":true,"video_link":"-NIME9XRqlo","schedule_release":null,"display_editors":true,"is_directory_listing":false,"is_splunk_built":false,"cloud_compatible":false,"archive_status":"live","is_archived":false,"is_never_archived":false,"fedramp_validation":"no"}


"""
