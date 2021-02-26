from jira import JIRA
import yaml
import json
import pandas as pd
import json
import sys
from datetime import datetime

def read_yaml(fname):
    try:
        with open(fname,'rt', encoding='utf8') as file:
            Od=yaml.load(file,Loader=yaml.FullLoader)   
            print(fname+' file read!')
            return Od
    except:
            print('Failed reading file '+fname+'!')
    
def update_field_mappings(jira_conn,fname):
    mappings = read_yaml(fname)
    allfields=jira_conn.fields()
    update={}
    # Make a map from field name -> field id
    nameMap = {field['name']:field['id'] for field in allfields}
    for i,j in nameMap.items():
        if i not in mappings.keys():
            if 'fields.'+str(j) != mappings.get(i):
                update[i] = 'fields.'+str(j)
    if len(update)!=0:
        with open(fname, 'a') as f:
            f.write('\n')
            yaml.dump(update,f,encoding='utf8')
    else:
        pass
          

def Jira_conn(user,apikey,server):
    options = {'server': server}
    try:
        #jira_conn = JIRA('https://jira.atlassian.com')
        jira_conn = JIRA(options, basic_auth=(user,apikey) )
        print('Connection to jira established!')
    except:
        print('Connection to jira failed!Check credentials')
    return jira_conn

def get_projects_in_server(jira_conn):
    project_list=[]
    for i in jira_conn.projects():
        project_list.append(i.name)
    return project_list

    
def get_all_issues(jira,proj,jql,filter=0):
    print('Fetching issues for project='+proj+'.......')
    block_size = 100
    block_num = 0
    allissues = []
    while True:
        issues=[]
        start_idx = block_num*block_size
        if len(jql)!=0:
            issues = jira.search_issues('project= '+proj+' AND '+jql, start_idx, block_size,json_result=True)   
        elif filter!=0:
            issues = jira.search_issues('filter='+str(filter), start_idx, block_size,json_result=True)
            print(len(issues))
        else:
            issues = jira.search_issues('project='+proj, start_idx, block_size,json_result=True)
        if len(issues['issues']) == 0:
             # Retrieve issues until there are no more to come
            break
        block_num += 1
        #print(issues)
        for issue in issues['issues']:
            allissues.append(issue)
    return allissues

def rename_cols(df,fields,exclude_cols):
    df = df
    mappings = read_yaml('mappings.yaml')
    d={}
    if len(exclude_cols)!=0:
        print('Excluding columns....')
        for i in exclude_cols:
            l = [c for c in df.columns if re.search(i,c.lower()) == None]
            df=df[l]
    for col in list(df.columns):
        for i,j in mappings.items():
            if str(j) == str(col):
                d[str(col)] = str(i)
            elif re.search(str(j), str(col)) != None:
                d[str(col)] = re.sub(str(j),str(i), str(col))   
    df= df.rename(columns= d)
    if len(fields)!=0:
        print('Selecting desired columns....')
        cols = []
        for i in fields:
            cols.extend([c for c in df.columns if re.search(i,c) != None])
        df = df[cols]
    return df
	
def saveAsSeperateSheets(jira_conn,projects,jql,fname,fields,exclude_cols):
    now = datetime.now()
    ts_now = str(now.strftime("%m-%d-%Y_%H.%M.%S"))
    fname = fname+'_'+ts_now+".xlsx"
    writer = pd.ExcelWriter(fname, engine='xlsxwriter')
    for project in projects:
        allissues_details = get_all_issues(jira_conn,project,jql)
        issue_df = pd.json_normalize(allissues_details)
        issue_df = rename_cols(issue_df,fields,exclude_cols)
        print('Writing sheet '+project+'_issues.....')
        issue_df.to_excel(writer, sheet_name=project+'_issues',index=False,encoding='utf-8') 
    print('Saving file '+fname+".....")
    writer.save()
    
def saveAsSeperateFiles(jira_conn,projects,jql,fields,exclude_cols):
    for project in projects:
        allissues_details = get_all_issues(jira_conn,project,jql)
        issue_df = pd.json_normalize(allissues_details)
        issue_df = rename_cols(issue_df,fields,exclude_cols)
        now = datetime.now()
        ts_now = str(now.strftime("%m-%d-%Y_%H.%M.%S"))
        fname = project+'_'+ts_now+'.xlsx'
        writer = pd.ExcelWriter(fname, engine='xlsxwriter')
        print('Saving file '+fname+".....")
        issue_df.to_excel(writer, sheet_name=project+'_issues',index=False,encoding='utf-8') 
        writer.save()
        print('\n\n')
    
def saveAsSingleSheet(jira_conn,projects,jql,fname,fields,exclude_cols,filters=0):
    now = datetime.now()
    ts_now = str(now.strftime("%m-%d-%Y_%H.%M.%S"))
    fname = fname+'_'+ts_now+".xlsx"
    writer = pd.ExcelWriter(fname, engine='xlsxwriter')
    final_df = pd.DataFrame()
    if filters!=0:
        final_df = execute_filter(jira_conn,fname,exclude_cols,fields,filters)
    else:
        for project in projects:
            allissues_details = get_all_issues(jira_conn,project,jql)
            issue_df = pd.json_normalize(allissues_details)
            issue_df = rename_cols(issue_df,fields,exclude_cols)
            final_df = pd.concat([final_df,issue_df], axis=0, ignore_index=True)
    print('Writing issues to file '+fname+'.....')
    print('....',final_df.shape)
    final_df.to_excel(writer, sheet_name='Issues',index=False,encoding='utf-8') 
    print('Saving file '+fname+".....")
    writer.save()    

def execute_filter(jira_conn,fname,exclude_cols,fields,filters):
    final_df = pd.DataFrame()
    allissues_details = get_all_issues(jira_conn,'','',filter=filters)
    issue_df = pd.json_normalize(allissues_details)
    issue_df = rename_cols(issue_df,fields,exclude_cols)
    return issue_df
	
def create_reports():
    conf = read_yaml('config.yaml')
    user = conf['user']
    apikey = conf['apikey']
    server = conf['server']
    jira_conn = Jira_conn(user,apikey,server)
    
    fname = conf['op_filename']
    exclude_cols = conf['exclude_field_val']
    jql= conf['jql']
    filters=conf['filter']
    fields= conf['fields']
    output_option = conf['output_option']
    projects = conf['projects']
    if len(projects)==0:
        projects=get_projects_in_server(jira_conn)
    if conf["update_field_mappings"]==True:
        update_fields = update_field_mappings(jira_conn,'mappings.yaml')
    if output_option==1:
        saveAsSingleSheet(jira_conn,projects,jql,fname,fields,exclude_cols,filters)  
    elif output_option==2:
        saveAsSeperateFiles(jira_conn,projects,jql,fields,exclude_cols)
    elif output_option==3:
        saveAsSeperateSheets(jira_conn,projects,jql,fname,fields,exclude_cols)
    else:
        print('-----Invalid save option-----')
    
def create_reports():
    conf = read_yaml('config.yaml')
    user = conf['user']
    apikey = conf['apikey']
    server = conf['server']
    jira_conn = Jira_conn(user,apikey,server)
    
    fname = conf['op_filename']
    exclude_cols = conf['exclude_field_val']
    jql= conf['jql']
    filters=conf['filter']
    fields= conf['fields']
    output_option = conf['output_option']
    projects = conf['projects']
    if len(projects)==0:
        projects=get_projects_in_server(jira_conn)
    if conf["update_field_mappings"]==True:
        update_fields = update_field_mappings(jira_conn,'mappings.yaml')
    if output_option==1:
        saveAsSingleSheet(jira_conn,projects,jql,fname,fields,exclude_cols,filters)  
    elif output_option==2:
        saveAsSeperateFiles(jira_conn,projects,jql,fields,exclude_cols)
    elif output_option==3:
        saveAsSeperateSheets(jira_conn,projects,jql,fname,fields,exclude_cols)
    else:
        print('-----Invalid save option-----')
    
if __name__=="__main__":
	create_reports()
	