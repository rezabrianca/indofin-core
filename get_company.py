#!/usr/bin/python3
import os
import time
import pandas as pd

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select

from db import pg_connect
from slack_message import sendMessage

os.chdir('/home/ubuntu/indofin-core/')
today = pd.to_datetime('today').strftime('%Y-%m-%d')
snapshot_at = pd.to_datetime('today').date()
sendMessage('Begin cron job at {0}'.format(today))

# setup
opts = Options()
opts.set_headless()
opts.add_argument('log-level=3') # suppress warning
opts.add_argument('--no-sandbox')

assert opts.headless
browser = Chrome('/usr/bin/chromedriver', options=opts)

browser.implicitly_wait(1)
print(os.getcwd())

try:
    # open web page
    browser.get('https://www.idx.co.id/perusahaan-tercatat/profil-perusahaan-tercatat/')

    # select page to display 100 company in a page
    select = Select(browser.find_element_by_name('companyTable_length'))
    number_per_page = int(select.options[3].text)
    select.select_by_value('100')
    time.sleep(2)
    
    # get data in the first page
    print('Retrieve data in page 1 ...')
    company_table = browser.find_element_by_id('companyTable').text.split('\n')
    company_raw = [company_table[i].split() for i in range(1, len(company_table))] # first row is header
    company_code = [company_raw[i][1] for i in range(len(company_raw))] # company stock code
    company_name = [' '.join(company_raw[i][2:-3]) for i in range(len(company_raw))] # company registered name
    date_public = [' '.join(company_raw[i][-3:]) for i in range(len(company_raw))] # company date of went public

    # first page data as dataframe
    company_df = pd.DataFrame({'company_code':company_code, 'company_name':company_name, 'Tanggal Pencatatan':date_public})

    # get page number to fetch
    page_element = browser.find_elements_by_class_name('paginate_button ')
    time.sleep(2)

    # first and last element is 'Previous' and 'Next'
    page_element_length = len(browser.find_elements_by_class_name('paginate_button '))-1
    time.sleep(2)

    # retrieve data in the next page (start from 2nd page since we already got the 1st page)
    for i in range(2, page_element_length):
        print('Retrieve data in page {0} ...'.format(i))
        browser.find_elements_by_class_name('paginate_button ')[i].click()
        time.sleep(2)
        company_table = browser.find_element_by_id('companyTable').text.split('\n')
        company_raw = [company_table[i].split() for i in range(1, len(company_table))]
        company_code = [company_raw[i][1] for i in range(len(company_raw))]
        company_name = [' '.join(company_raw[i][2:-3]) for i in range(len(company_raw))]
        date_public = [' '.join(company_raw[i][-3:]) for i in range(len(company_raw))]
        company_df_add = pd.DataFrame({'company_code':company_code, 'company_name':company_name, 'Tanggal Pencatatan':date_public})

        # append company information
        company_df = company_df.append(company_df_add, ignore_index=True)

    company_df['snapshot_at'] = snapshot_at
    company_df = company_df.drop('Tanggal Pencatatan', axis=1)

    conn = pg_connect()
    print('Writing active company at {0} to active company history'.format(today))

    # store in active company history
    company_df.to_sql('active_company_history', conn, schema='company', if_exists='append', index=False)

    print('There are {0} public companies at {1}'.format(company_df.shape[0], today))
    sendMessage('There are {0} public companies at {1}'.format(company_df.shape[0], today))

    with open('sql/get_active_company.sql', 'r') as f:
        query = f.read()
        f.close()
    active_company = pd.read_sql(query, conn)
    print('Writing latest company list to active company')
    active_company.to_sql('active_company', conn, schema='company', if_exists='replace', index=False)

except Exception as e:
    print('Error Type:', e.__class__.__name__)
    print('Error Message:', e)

finally:
    # close the browser
    browser.close()
    quit()
