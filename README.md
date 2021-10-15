# C Header to XML

Converts a C header to an XML file suitable for [API Monitor](http://www.rohitab.com/apimonitor).

## Limitiations

* it isn't automatic, you have to run the file through the C preprocessor manually
* you might need to add some typedefs, e. g. `typedef int BOOL` to keep BOOL as typename
* it is used for one specific header currently

## Installation

* copy `api.xml` to `%ChocolateyInstall%\lib\apimonitor\tools\API Monitor (rohitab.com)\API`
* apparently only the extension `.xml`, not `.h.xml` is accepted


