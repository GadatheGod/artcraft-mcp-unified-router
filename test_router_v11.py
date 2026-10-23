import unittest
from artcraft_unified_router import Router, Child
class RouterV11Tests(unittest.TestCase):
 def test_alias_and_catalog(self):
  r=Router({'primary_app':'SolidCraft','apps':{}})
  c=Child('SolidCraft',{'command':['dummy']},lambda _:None)
  c.ready=True;c.tools=[{'name':'list_commands','description':'list','inputSchema':{'type':'object','properties':{}}},{'name':'execute','inputSchema':{'type':'object'}}]
  c.request=lambda method,params,timeout:{'result':{'content':[{'type':'text','text':'ok'}]}}
  r.apps['SolidCraft']=c;r.rebuild()
  names={t['name'] for t in r.list_tools()}
  assert {'list_commands','execute','solidcraft__list_commands','solidcraft__execute','artcraft_catalog'}<=names
  assert r.call_tool('list_commands',{})['content'][0]['text']=='ok'
  assert len(__import__('json').loads(r.call_tool('artcraft_catalog',{})['content'][0]['text'])['SolidCraft']['tools'])==2
 def test_other_apps_namespaced(self):
  r=Router({'primary_app':'SolidCraft','apps':{}})
  c=Child('GridCraft',{'command':['dummy']},lambda _:None);c.ready=True;c.tools=[{'name':'execute','inputSchema':{'type':'object'}}]
  r.apps['GridCraft']=c;r.rebuild()
  assert 'gridcraft__execute' in r.mapping and 'execute' not in r.mapping
if __name__=='__main__':unittest.main()