
Build example
-------------


Take a look at this example :file:`build.py` file that use the :py:mod:`ksconf.builder` module.


..  literalinclude:: _static/build.py
    :language: python
    :linenos:
    :name: build.py


Usage notes
~~~~~~~~~~~

*   :py:class:`~ksconf.builder.core.BuildManager` - is used to help orchestrate the build process.
*   ``step`` is an instance of :py:class:`~ksconf.builder.BuildStep`, which is passed as the first argument to all the of step-service functions.
    This class assists with logging, and directing all activities to the correct paths.
*   There's no interal interface for :ref:`ksconf_cmd_package` yet, hence another instance of Python is launched on line 48.
    This is done using the module execution mode of Python, which is a slightly more reliable way of launching ksconf from within itself.
    For whatever that's worth.
