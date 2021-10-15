import xml.etree.ElementTree as ET
from header2apimonitor import ApiMonitorTypes


simple = '''
<ApiMonitor>
<Headers>
        <Condition Architecture="32">
            <Variable Name="INT_PTR"    Type="Integer"  Size="4" />
            <Variable Name="UINT_PTR"   Type="Integer"  Size="4" Unsigned="True" />
        </Condition>
</Headers>
</ApiMonitor>
'''


def test_simple():
    obj = ApiMonitorTypes()
    obj.parse(ET.fromstring(simple))
    assert not obj.is_defined('int*')
    assert obj.is_defined('INT_PTR')
    assert obj.is_defined('UINT_PTR')

