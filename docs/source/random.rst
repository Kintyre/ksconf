Random
======

Typographic and Convention
**************************

Pronounced:   k·s·kȯnf



Capitalization:


============    ====================================
Form            Acceptability factor
============    ====================================
``ksconf``      Always lower for CLI.
                Generally preferred.
KSCONF          Okay for titles.
Ksconf          Title case is okay too.
KSConf          You'll see this, but weird.
KsConf          No, except maybe in a class name?
KsconF          Thought about it.
                Reserved for ASCII art ONLY
============    ====================================


   | I wrote this while laughing at my own lack of consistency.
   | Really don't care.
   | -- Lowell


.. _splunk conf updates:

How Splunk writes to conf files
-------------------------------

Splunk does some somewhat counter intuative thing when it writes to local conf files.

For example,

 1. All conf file updates are automatically minimized.  (Splunk can get away with this because it *only* updates "local" files.)
 2. Modified stanzas are removed from the current position in the .conf file and moved to the bottom.
 3. Stanzas are typically re-written sorted in attribute order.  (Or is it the same as #2, updated attributes are written to the bottom.)
 4. Sometimes boolean values persist in unexpected ways.  (Primarily this is because there's mor
    than one way to represent them textually, and that textual representation is different from
    what's stored in default)

Essentially, splunk will allways "minimize" the conf file at each any every update.  This is because
Splunk internally keeps track of the final representation of the entire stanza (in memory), and only
when it's written to disk does Splunk care about the the current contents of the local file.  In
fact, Splunk re-reads the conf file immidately before updating it.  This is why, if you've made a
local changes, and forgot to reload, Splunk will typically not lose your change (unless you've
update the same attribute both places... I mean, it's not magic.)


.. tip::  Don't believe me? Try it yourself.

   To prove that it works this way, simply find a savedsearch that you modified from any app that
   you installed.  Look at the local conf file and observe your changes.  Now go edit the saved
   search and restore some attribute to it's origional value (the most obvious one here would be the
   ``search`` attribute), but that's tricky if it's mulilined.  Now go look at the local conf file
   again.  If you updated it with *exactly* the same value, then that attribute will have been
   compeetly removed from the local file.  This is infact a neat trick that can be used to revert
   local changes to allow future updates to "pass-though" unimpedied.  In SHC scenarios, this may
   be your only option to remove local settings.

Okay, so what's the value in having a :ref:`minimize <ksconf_cmd_minimize>` command if Splunk does
this automatically every time it's makes a change?  Well, simply put, because Splunk can't write to
all local file locations.  Splunk only writes to system, etc/users, and etc/apps local folders (and
sometimes to deployment-apps app.conf local file, but that's a completely different story.)

Also, there's also times where boolean values will show up in an unexpected manor because of how
Splunk treats them internally.  I'm still not sure if this is a silly mistake in the default .conf
files or a clever workaround to what's essentially a design flaw in the conf system.  But either
way, I suspect the user benefits.  Because splunk accepts more values as boolean than what it will
write out, this means that certain boolean values will always be explicitly store in the conf files.
This means that man ``disabled`` and bunches of other settings in ``savedsearches.conf`` always get
explicitly written.  How is that helpful?  Well, imagine what would happen if you accidentally
changed ``disabled = 1`` in the global stanzas in savedsearches.conf.  Well, *nothing* if all
savedsearches have that values explicitly written.  The point is this: there are times when
repeating yourself isn't a bad thing.  (Incidently, this is the reason for the ``--preserve-key``
flag on the :ref:`minimize <ksconf_cmd_minimize>` command.)



.. _Grandfather Paradox:

Grandfather Paradox
-------------------

The KSCONF Splunk app breaks it's designed paradigm (not in a good way).  Ksconf was designed to be
the thing that manages all your other apps, so by deploying ksconf as an app itself, we open up the
possiblity that ksconf could upgrade it self or deploy itself, or manage itself.   Basically it
could cut off the limb that it's standing on.   So practically this can get messy, especially if
you're on Windows where file locking is also likely to cause issues for you.

So sure, if you want to be picky, "Grandfather paradox" is probably the wrong annalogy.
Pull requests welcome.
