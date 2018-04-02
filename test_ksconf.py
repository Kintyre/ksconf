import unittest
from textwrap import dedent

from ksconf import *


# For coverage info, can be run with nose2, like so:
#  nose2 -s . -C



import warnings
# Don't warn us about tempnam, we can't use tmpfile, we need an named filesystem object
warnings.filterwarnings("ignore", "tempnam is a potential security.*", RuntimeWarning)


def parse_string(text, **kwargs):
    text = dedent(text)
    f = StringIO(text)
    return parse_conf(f, **kwargs)



class ParserTestCase(unittest.TestCase):
    """ Test the parse_conf() Splunk .conf parser.  We should be at least as string as Splunk. """

    # List of test to add yet:

    # Todo:  Test comments in general...  Don't go too deep into this beacuse we don't care too much, and eventually better comment support will break the API.
    # Todo:  Test trailing comments on stanzas
    # Todo:  Test trailing comments on key=value lines
    # Todo:  Test copy/deepcopy support:  Parse a string, copy, change origional, confirm copy wasn't altered.

    # Helper methods
    @staticmethod
    def parse_string(text, **kwargs):
        text = dedent(text)
        f = StringIO(text)
        return parse_conf(f, **kwargs)

    def test_read_file(self):
        """ Confirm that parse_conf() works with an OS-level file. """
        d = {
            "stanza1": {"key1": "value1", "key2": "value2"},
            "stanza2": {"monkey": "banana", "dog": "cat"},
        }
        tfile = os.tempnam()
        #tfile = os.tempnam(None, "ksconf-unitest-") + ".conf"
        try:
            write_conf(tfile, d)
            d2 = parse_conf(tfile)

            self.assertDictEqual(d, d2)
        finally:
            os.unlink(tfile)

    def test_multi_stanza(self):
        c = parse_string("""
        [stanza1]
        key1 = yes
        key2 = no
        [stanza2]
        key1 = no
        key2 = yes
        empty =
        """)
        self.assertEqual(c["stanza1"]["key1"], "yes")
        self.assertEqual(c["stanza1"]["key2"], "no")
        self.assertEqual(c["stanza2"]["key1"], "no")
        self.assertEqual(c["stanza2"]["key2"], "yes")
        self.assertEqual(c["stanza2"]["empty"], "")

    def test_preserve_empty_stanza(self):
        c = parse_string("""
        [stanza1]
        key1 = yes
        key2 = no
        [stanza2]
        
        [stanza3]
        has_key = true
        """)
        self.assertEqual(c["stanza1"]["key1"], "yes")
        self.assert_("stanza2" in c, "Must preserve empty stanza")
        self.assertEqual(len(c["stanza2"]), 0)
        self.assertEqual(c["stanza3"]["has_key"], "true")

    def test_whitespace_keyvalue(self):
        c = parse_string("""
        [stanza1]
        key1=yes
        key2  =   no
        [stanza2]
         key1 =\tred
        key with spaces = not normal
        key2 = green   """)  # Trailing white space on key2
        self.assertEqual(c["stanza1"]["key1"], "yes")
        self.assertEqual(c["stanza1"]["key2"], "no")
        # XXX: This seems wrong...  we probably don't want to preserve whitespace in the key name.
        self.assertEqual(c["stanza2"][" key1"], "red")
        # Todo: Figure out what Splunk behavior is for trailing whitespace.  (For now, should pass)
        self.assertEqual(c["stanza2"]["key2"], "green   ")
        # Todo:  Does this ever happen...
        self.assert_(c["stanza2"]["key with spaces"])

    def test_whitespace_stanza(self):
        c = parse_string("""
        [stanza 1]
        type = bool
        value = False
        [ stanza2]
        color = yellow
        [stanza 3 ]
        homework = no
         [stanza 4]
        pre_whitespace = weird
        [stanza 5]  """)
        self.assertEqual(c["stanza 1"]["type"], "bool")
        self.assertEqual(c[" stanza2"]["color"], "yellow")
        self.assertEqual(c["stanza 3 "]["homework"], "no")
        # This one fails....   need to confirm Splunk's built-in behavior....  Maybe this should fail on 'strict' mode?
        #self.assertEqual(c["stanza 4"]["pre_whitespace"], "weird")
        self.assertIn("stanza 5", c)

    def test_stanza_weird_chars(self):
        c = parse_string(r"""
        [source::...(/|\\)var(/|\\)log(/|\\)splunk(/|\\)*aws_sns*.log*]
        LINE_BREAKER=([\r\n]+)\d{4}-\d{2}-\d{2}
        sourcetype = aws:sns:alert:log
        priority = 1
        
        [source::...[/\\]var[/\\]log[/\\]splunk[/\\]s3util*.log*]
        sourcetype = aws:s3util:log
        priority = 10
        
        [My cool search [COOLNESS]]
        search = ...
        """)
        self.assert_(c[r"source::...(/|\\)var(/|\\)log(/|\\)splunk(/|\\)*aws_sns*.log*"])
        self.assert_(c[r"source::...[/\\]var[/\\]log[/\\]splunk[/\\]s3util*.log*"])
        self.assert_(c["My cool search [COOLNESS]"])

    def test_global_stanzs(self):
        c = parse_string("""
        animal = dog
        [jungle]
        animal = monkey
        [forest]
        animal = wolf
        """)  # Trailing white space on key2
        self.assertEqual(c[GLOBAL_STANZA]["animal"], "dog")
        self.assertEqual(c["jungle"]["animal"], "monkey")
        self.assertEqual(c["forest"]["animal"], "wolf")

    @unittest.expectedFailure
    def test_bad_stanza(self):
        t1 = """
        [Errors in the last hour
        search = error OR failed OR severe OR ( sourcetype=access_* ( 404 OR 500 OR 503 ) )
        dispatch.earliest_time = -1h
        """
        t2 = """
        [Errors in the last hour
        ]
        search = error OR failed OR severe OR ( sourcetype=access_* ( 404 OR 500 OR 503 ) )
        dispatch.earliest_time = -1h
        """
        t3 = """
        Errors in the last hour]
        search = error OR failed OR severe OR ( sourcetype=access_* ( 404 OR 500 OR 503 ) )
        dispatch.earliest_time = -1h
        """
        # These SHOULD raise an error, even without strict=True
        with self.assertRaises(ConfParserException):
            parse_string(t1)

        with self.assertRaises(ConfParserException):
            parse_string(t2)

        with self.assertRaises(ConfParserException):
            parse_string(t3)

    def test_dup_keys(self):
        t = """
        [jungle]
        animal = monkey
        animal = snake
        [forest]
        animal = wolf
        """
        with self.assertRaises(DuplicateKeyException):
            self.parse_string(t, dup_key=DUP_EXCEPTION)

        c = self.parse_string(t, dup_key=DUP_MERGE)
        self.assertEqual(c["jungle"]["animal"], "snake")
        self.assertEqual(c["forest"]["animal"], "wolf")

    def test_dup_stanzas(self):
        t = """
        [jungle]
        animal = monkey
        key2 = 01
        
        [forest]
        animal = wolf
        
        [jungle]
        animal = snake
        """
        with self.assertRaises(DuplicateStanzaException):
            parse_string(t, dup_stanza=DUP_EXCEPTION)

        c = parse_string(t, dup_stanza=DUP_MERGE)
        self.assertEqual(c["jungle"]["animal"], "snake")
        self.assertEqual(c["jungle"]["key2"], "01")
        self.assertEqual(c["forest"]["animal"], "wolf")

        c = parse_string(t, dup_stanza=DUP_OVERWRITE)
        self.assertEqual(c["jungle"]["animal"], "snake")
        with self.assertRaises(KeyError):
            c["jungle"]["key2"]
        self.assertEqual(c["forest"]["animal"], "wolf")

    def test_strict_junk(self):
        t = """
        [stanza]
        key1 = an every-day value
        a random line of text that's not a key/value pair
        key2 = normalness
        """
        with self.assertRaises(ConfParserException):
            parse_string(t, strict=True)

    def test_continuation(self):
        t = r"""
        [Sourcetype regex reuse]
        description = Determining similarities in sourcetypes based on which share the same EXTRACT regexes
        dispatch.earliest_time = 0
        display.general.type = statistics
        display.page.search.tab = statistics
        display.visualizations.show = 0
        search = | rest /servicesNS/-/-/configs/conf-props \
        | search eai:appName=* NOT title=source::* \
        | table title, EXTRACT-*, TIME_FORMAT, TIME_PREFIX, LINE_BREAKER, SHOULD_LINEMERGE, KV_MODE, sourcetype \
        | rename title as sourcetype \
        | untable sourcetype key value \
        | search key="EXTRACT-*" \
        | eval entry="[".sourcetype . "] " . key \
        | stats count values(entry) as entry by value \
        | where count>1
        """
        c = parse_string(t)
        self.assertEqual(len(c["Sourcetype regex reuse"]["search"].splitlines()), 9)

    def test_continuation_subsearch(self):
        """ Need to make sure that []"""
        t = r"""
        [Knowledge Object backup to CSV]
        description = Useful tool to export Knowledge Objects when (1) you don't have file-system \
        access, and (2) you only have Splunk Web access (no REST calls).
        search = | makeresults count=1 | \
        eval id="BACKUP-HEADER", now=now(), \
          title="BACKUP DESCRIPTION GOES HERE" \
        | append \
        [ rest splunk_server=local /servicesNS/-/-/data/ui/views ] \
        | append \
        [ rest splunk_server=local /servicesNS/-/-/configs/conf-macros ]
        request.ui_dispatch_view = search
        """
        c = parse_string(t)
        # If an empty global stanza is created, that's an implementation detail not important here.
        if GLOBAL_STANZA in c and not c[GLOBAL_STANZA]:
            del c[GLOBAL_STANZA]
        self.assert_(c["Knowledge Object backup to CSV"])
        self.assertNotIn(" rest splunk_server=local /servicesNS/-/-/configs/conf-macros ", c)
        self.assertEqual(len(c), 1, "Should only have 1 stanza")
        self.assertEqual(len(c["Knowledge Object backup to CSV"]["search"].splitlines()), 7)


#@unittest.expectedFailure()




class ConfigDiffTestCase(unittest.TestCase):

    cfg_macros_1 = """
    [comment(1)]
    args = text
    definition = ""
    iseval = 1
    """

    cfg_props_imapsync_1 = r"""
    [other1]
    [imapsync]
    DATETIME_CONFIG =
    LINE_BREAKER = ([\r\n]+)(?:msg |PID|Writing|Folders |Host[12]|\+\+\++|Command|Log|Sending:|Modules version list)
    NO_BINARY_CHECK = true
    SHOULD_LINEMERGE = false
    TRUNCATE = 1000000
    category = Custom
    disabled = false
    pulldown_type = true
    """

    cfg_props_imapsync_2 = r"""
    [other2]
    
    [imapsync]
    LINE_BREAKER = ([\r\n]+)(?:msg |PID|Writing|Folders |Host[12]|\+\+\++|Command|Log|Sending:|Modules version list)
    TRUNCATE = 1000000
    NO_BINARY_CHECK = false
    category = Custom
    description = IMAP Sync tool
    pulldown_type = true
    """

    @staticmethod
    def find_op_by_location(diffs, type, **kwargs):
        for op in diffs:
            if op.location.type == type:
                match = True
                for (attr, value) in kwargs.iteritems():
                    if getattr(op.location, attr, None) != value:
                        match = False
                        break
                if match:
                    return op

    def test_compare_keys_props(self):
        c1 = parse_string(self.cfg_props_imapsync_1)
        c2 = parse_string(self.cfg_props_imapsync_2)
        diffs = compare_cfgs(c1, c2)

        op = self.find_op_by_location(diffs, "key", stanza="imapsync", key="NO_BINARY_CHECK")
        self.assertEqual(op.tag, DIFF_OP_REPLACE)
        self.assertEqual(op.a, "true")
        self.assertEqual(op.b, "false")

        op = self.find_op_by_location(diffs, "key", stanza="imapsync", key="LINE_BREAKER")
        self.assertEqual(op.tag, DIFF_OP_EQUAL)
        self.assertEqual(op.a, op.b)
        self.assert_(op.a.startswith(r"([\r\n]+)"))   # Don't bother to match the whole thing...

        op = self.find_op_by_location(diffs, "key", stanza="imapsync", key="DATETIME_CONFIG")
        self.assertEqual(op.tag, DIFF_OP_DELETE)
        self.assertIsNone(op.a)
        self.assertIsNotNone(op.b)

        op = self.find_op_by_location(diffs, "key", stanza="imapsync", key="description")
        self.assertEqual(op.tag, DIFF_OP_INSERT)
        self.assertIsNotNone(op.a)
        self.assertIsNone(op.b)




class ConfigMergeTestCase(unittest.TestCase):

    @staticmethod
    def merge(*cfg_txts, **parse_args):
        dicts = [ parse_string(txt, **parse_args) for txt in cfg_txts ]
        return merge_conf_dicts(*dicts)

    def test_merge_simple_2(self):
        d = self.merge("""
        [x]
        a = 1
        [y]
        b = 2
        [z]
        ""","""
        [x]
        a = one
        [y]
        c = 3
        """)
        self.assertEqual(d["x"]["a"], "one")
        self.assertEqual(d["y"]["b"], "2")
        self.assertEqual(d["y"]["c"], "3")
        self.assertIn("z", d)


class UtilFunctionTestCase(unittest.TestCase):
    
    def test_relwalk_prefix_preserve(self):
        a = list(relwalk("."))
        b = list(relwalk("." + os.path.sep))
        print b
        self.assertListEqual(a, b, "should return the same paths with or without a trailing slash")


if __name__ == '__main__':
    unittest.main()
