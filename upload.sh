#!/bin/bash
APP_ID=4383

echo curl -u lalleman --request POST https://splunkbase.splunk.com/api/v1/app/${APP_ID}/new_release/ -F "files[]=@$(<.release_path)" -F "filename=$(<.release_name)" -F "splunk_versions=7.2,7.3,8.0,8.1" -F "visibility=false"
curl -u lalleman --request POST https://splunkbase.splunk.com/api/v1/app/${APP_ID}/new_release/ -F "files[]=@$(<.release_path)" -F "filename=$(<.release_name)" -F "splunk_versions=7.2,7.3,8.0,8.1" -F "visibility=false"
