import unittest, json, tempfile
from artcraft_unified_router import Router, Child
class RouterTests(unittest.TestCase):
 def test_stable_tools(self):
  r=Router({'apps':{}})
  names={t['name'] for t in r.list_tools()}
  self.assertTrue({'artcraft_status','artcraft_refresh','artcraft_apps','artcraft_tools','artcraft_execute'} <= names)
 def test_app_lookup(self):
  r=Router({'apps':{}})
  r.apps['GridCraft']=Child('GridCraft',{'command':['dummy']},lambda x:None)
  self.assertEqual(r.find_app('gridcraft').name,'GridCraft')
 def test_dispatch(self):
  r=Router({'apps':{}})
  c=Child('GridCraft',{'command':['dummy']},lambda x:None)
  c.ready=True;c.tools=[{'name':'sheet.create','inputSchema':{'type':'object'}}]
  c.request=lambda method,params,timeout:{'result':{'content':[{'type':'text','text':'ok'}]}}
  r.apps['GridCraft']=c
  result=r.call_tool('artcraft_execute',{'app':'gridcraft','tool':'sheet.create','arguments':{}})
  self.assertEqual(result['content'][0]['text'],'ok')
if __name__=='__main__':unittest.main()