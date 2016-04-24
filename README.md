Needy [![Build Status](https://travis-ci.org/ccbrown/needy.svg?branch=master)](https://travis-ci.org/ccbrown/needy)
==

Needy is tool that aims to make C++ library dependencies as magical as possible. Dependencies are declared in a file called known as the "needs file", usually by simply adding a download URL and checksum. Then Needy will download and build those dependencies for you.

For example, by creating a *need.yaml* file in your project that looks like...

```yaml
libraries:
    catch:
        repository: git@github.com:philsquared/Catch.git
        commit: v1.3.0
```

...a simple command invocation (`needy satisfy`) will download and build [Catch](https://github.com/philsquared/Catch) for you. Once integrated with your build system, adding, updating, or modifying dependencies in any way becomes a trivial matter.

Needy is extremely capable, so be sure to check out [the documentation](https://ccbrown.github.com/needy) to see some more things you can do.
