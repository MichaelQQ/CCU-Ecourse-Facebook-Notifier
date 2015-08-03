#-*- coding:utf-8 -*-
import mechanize
import getpass
from bs4 import BeautifulSoup

LOGIN_URL = 'http://ecourse.elearning.ccu.edu.tw/'

def get_announcements(username, password):
    try:
        #Setup mechanize browser
        browser = mechanize.Browser()
        browser.set_handle_robots(False)
        browser.addheaders =[('User-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.114 Safari/537.36')]

        #Connect to login URL
        browser.open(LOGIN_URL)
        #print 'Login page: connected!'

        #Select the form, nr=0 means to use the first form you find
        #Else enter the name='form ID name'
        browser.select_form(nr=0)# name="login_form"

        #Fill the username and password in the form
        #Might have to check your particular webpage for actual name of input id
        browser['id'] = username
        browser['pass'] = password

        #Clicks the submit button for a particular form
        result = browser.submit()
        #print 'Login page: accessing...'
        URL2 = result.geturl()
        ssid =  URL2[-36:]

        ANNOUNCE_LIST =[]
        LIST_URL = 'http://ecourse.elearning.ccu.edu.tw/php/Courses_Admin/take_course.php?' + ssid
        result = browser.open(LIST_URL+'&frame=1')
        html = result.read()
        soup = BeautifulSoup(html)
        link = soup.find_all('table')[1].find_all('a', target="_top")
        #Cal total course number and open COURSE URL
        total_course_num = len(link)
        for course_num in range(total_course_num):
            course_name = link[course_num].text
            COURSE_URL = link[course_num]['href']
            result = browser.open(COURSE_URL)

            NEWS_URL = 'http://ecourse.elearning.ccu.edu.tw/php/news/news.php?' + ssid
            result = browser.open(NEWS_URL)
            html2 = result.read()
            soup2 = BeautifulSoup(html2)
            link2 = soup2.find_all('a', href='#')
            total_annoc_num = len(link2)
            if total_annoc_num > 1:
                total_annoc_num = 1

            for annoc_num in range(total_annoc_num):
                output = []
                output.append(course_name)
                ANNOC_URL = 'http://ecourse.elearning.ccu.edu.tw/php/news' + link2[annoc_num]['onclick'].split("'")[1][1:]
                result = browser.open(ANNOC_URL)
                annochtml = result.read()
                table_one = BeautifulSoup(annochtml).find_all('table')
                for value in table_one[1].find_all('div'):
                    output.append(value.text)
                #Couse_Name:Title(Time)\n data
                ANNOUNCE = output[0]+':'+output[2]+'('+output[4]+')\n'+output[6]
                ANNOUNCE_LIST.append(ANNOUNCE)
        return ANNOUNCE_LIST
    except:
        return 'Error in get_announcements'
