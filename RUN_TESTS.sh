function RUN() {
    local expect_rc=${RC:-0}
    echo "Running:    ksconf $*  [Expect rc=$expect_rc]"
    coverage run -a ksconf.py $*
    rc=$?
    if [[ $rc -ne $expect_rc ]]
    then
        echo "Failed with exit code of $rc (expected $expect_rc)"
        echo "[$(basename "$BASH_SOURCE"):$BASH_LINENO]   ./ksconf.py $*  [rc=$rc]"
        exit 1
    fi
}

DOWNLOADS=$PWD/app_archive

coverage run run_tests.py || { echo "Unit test failed.  Stopping."; exit 2; }
#coverage report ksconf.py

RUN combine TEST_APPS/search/default.d/* --target=TEST_APPS/search/default --dry-run
touch TEST_APPS/search/default/EXTRA_FILE.conf
touch TEST_APPS/search/default/EXTRA_FILE.swp
touch TEST_APPS/search/default/EXTRA_FILE.bak
RUN combine TEST_APPS/search/default.d/* --target=TEST_APPS/search/default
# Test internal wildcard expansion
RUN combine 'TEST_APPS/search/default.d/*' --target=TEST_APPS/search/default
RC=1 RUN merge TEST_APPS/search/default.d/*/savedsearches.conf
RC=0 RUN merge TEST_APPS/search/default.d/*/savedsearches.conf --target=savedsearches.conf --dry-run
RC=1 RUN merge TEST_APPS/search/default.d/*/savedsearches.conf --target=savedsearches.conf
RC=3 RUN diff TEST_APPS/search/default.d/05-*/savedsearches.conf savedsearches.conf
RC=3 RUN diff TEST_APPS/search/default.d/05-*/savedsearches.conf savedsearches.conf --output=savedsearches.conf.diff

RUN promote savedsearches.conf TEST_APPS/search/default/savedsearches.conf --batch --keep
RUN promote savedsearches.conf TEST_APPS/search/default/savedsearches.conf --batch --keep-empty

rm TEST_APPS/search/local/bad_conf.conf
RUN check TEST_APPS/search/local/*.conf
find . -name '*.conf' | RUN check -
echo -e "[Badconf\nfile=True\n" > TEST_APPS/search/local/bad_conf.conf
RC=20 RUN check --quiet TEST_APPS/search/local/*.conf non-existant-file.conf


RC=1 RUN merge TEST_APPS/search/default.d/*/savedsearches.conf --target=savedsearches.conf
RUN promote savedsearches.conf TEST_APPS/search/default/savedsearches.conf --batch

RC=1 RUN merge TEST_APPS/search/default.d/*/savedsearches.conf --target=savedsearches.conf
RUN sort savedsearches.conf
RUN sort -i savedsearches.conf
echo -e "\n\n[stanza]\search=|noop\n[zzzblah]other=true\n" >> savedsearches.conf
RC=9 RUN sort -i savedsearches.conf

#coverage report ksconf.py

cp TEST_APPS/search/local/savedsearches.conf .
RC=3 RUN minimize TEST_APPS/search/default.d/05-*/savedsearches.conf --target=savedsearches.conf --dry-run
RUN minimize TEST_APPS/search/default.d/05-*/savedsearches.conf --target=savedsearches.conf

# Test with a .zip file
( cd apps || exit 9 ; git rm -rf TA_RSA_SecurIdApp; git commit TA_RSA_SecurIdApp -m "Deleted stuff"; )
RUN unarchive --dest=apps --allow-local --git-mode=stage --app-name=TA_RSA_SecurIdApp $DOWNLOADS/technology-add-on-for-rsa-securid_01.zip
(cd apps || exit 9; git commit . -m "Blind commit."; )

( cd apps || exit 9 ; git rm -rf cisco_ios; git commit cisco_ios -m "Deleted stuff"; )
RUN unarchive --dest=apps/ --default-dir="default.d/10-splunk" --exclude 'samples/...' --git-mode=commit $DOWNLOADS/cisco-ios_200.tgz --no-edit

for app in $DOWNLOADS/splunk-add-on-for-*.tgz; do RUN unarchive --dest=apps/ --default-dir="default.d/10-splunk" --exclude 'samples/*' --exclude eventgen.conf --exclude "static/..." --git-mode=commit --exclude=eventgen.com --keep='default.d/...' --keep=CUSTOM_MAGIC.txt --no-edit $app; done

[[ -f apps/Splunk_TA_aws/default.d/50-lowell/savedsearches.conf ]] && RC=3 RUN diff apps/Splunk_TA_aws/default.d/10-splunk/savedsearches.conf apps/Splunk_TA_aws/default.d/50-lowell/savedsearches.conf

coverage report ksconf.py
coverage html ksconf.py
