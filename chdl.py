#!venv/bin/python

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from uuid import uuid1
from glob import glob
from os.path import join as path_join
from os.path import sep

def get_chunk_urls(churl):
    from os import mkdir

    print("Get chunk urls from ", churl)
    options = webdriver.ChromeOptions()
    # options.add_argument('headless')

    driver = webdriver.Chrome(service=Service('./chromedriver'), options=options)
    driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": ["https://www.clubhouse.com/__log", "https://www.googletagmanager.com/*", "https://www.google-analytics.com/*"]})
    driver.execute_cdp_cmd('Network.enable', {})

    driver.implicitly_wait(5)
    driver.get(churl)
    salt = str(uuid1()).split("-")[0][:5]
    chuid = churl.split("?")[0].split("/")[-1]
    chdir = chuid + "_" + salt
    print("CH directory: ", chdir)

    try:
        mkdir(chdir)
    except Exception as e:
        print("Unable to make directory: ", repr(e))
        return

    wait = WebDriverWait(driver, 10)
    try:
        click_to_play = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".rounded-room p")))
        click_to_play.click()
    except Exception as e:
        print("Error in click_to_play: ", repr(e))

    room_name = driver.find_element(by=By.CSS_SELECTOR, value="#react-container h1").text
    try:
        title = driver.find_element(by=By.CSS_SELECTOR, value="#react-container h1:nth-child(2)").text
    except:
        title = ""

    try:
        audio = wait.until(EC.visibility_of_element_located((By.TAG_NAME, "audio")))
        sleep(2)
        duration = int(float(audio.get_attribute("duration")))
    except Exception as e:
        print("Error in finding audio element: ", repr(e))
        return

    currentTime = 0

    # if the script fails due to some reason, do not loop indefinitely. limit to 7200.
    while currentTime < duration and currentTime < 7200:
        print("{} %".format(int(100*currentTime/duration)))
        sleep(3)
        driver.execute_script("arguments[0].currentTime = arguments[1]", audio, currentTime)
        currentTime += 29

    # let the last chunk be requested
    sleep(5)

    res = driver.execute_script("return window.performance.getEntries();")
    driver.close()

    chunks = []

    for r in res:
        if r["name"].startswith("https://production"):
            chunks.append(r["name"])

    with open(path_join(chdir, "chunks"), "w") as fd:
        for c in chunks:
            fd.write(c + "\n")

    info = {"title": title, "room_name": room_name, "duration": duration}
    return chunks, chdir, info

def download_urls(urls, destdir):
    from urllib.request import urlretrieve
    done = 0
    for en, c in enumerate(urls):
        fn = str(en+1) + ".ts"
        try:
            print("Downloading url {}/{} ...".format(en+1, len(urls)))
            urlretrieve(c, path_join(destdir, fn))
            done += 1
        except Exception as e:
            print(repr(e))
    return done

def merge_chunks(chdir):
    from os.path import basename
    print("Merge chunks in ", chdir)
    ofname = path_join(chdir, "out.ts")
    out = open(ofname, "wb")
    # file not found
    fnf = 0
    for i in range(1, 1000):
        fname = path_join(chdir, str(i)) + ".ts"
        try:
            with open(fname, "rb") as fd:
                out.write(fd.read())
        except:
            fnf += 1
            if fnf >= 5:
                break
    out.close()
    return ofname

def convert_to_m4a(filepath, outpath):
    from subprocess import Popen
    print("Convert {} to {}".format(filepath, outpath))
    p = Popen(["ffmpeg", "-i", filepath, outpath])
    p.wait()

def write_info_verify(filepath, info):
    from os.path import basename
    from mutagen.mp4 import MP4

    aud = MP4(filepath)
    basepath = filepath[:-len(basename(filepath))]

    with open(path_join(basepath, "info"), "w") as fd:
        fd.write("title: " + info["title"] + "\n")
        fd.write("room: " + info["room_name"] + "\n")
        fd.write("duration: " + str(round(aud.info.length, 2)) + "\n")
        fd.write("fileinfo: " + aud.pprint() + "\n")

    durdiff = abs(info["duration"] - round(aud.info.length, 2))
    # decimals can be ignored. but all the chunks have to be present
    if durdiff < 1:
        open(path_join(basepath, "success"), "w").close()
        return True
    else:
        print("Difference in duration is ", durdiff)
        return False

def download_ch_audio(churl):
    try:
        chunks, chdir, info = get_chunk_urls(churl)
        count = download_urls(chunks, chdir)
    except Exception as e:
        print("Error in download_ch_audio: ", repr(e))
        return

    if len(chunks) != count:
        print("Some chunks have not been downloaded")

    fn = merge_chunks(chdir)

    convert_to_m4a(fn, path_join(chdir, "out.m4a"))

    if write_info_verify(path_join(chdir, "out.m4a"), info):
        print("Success on ", churl)
    else:
        print("Failure on ", churl)

if __name__ == "__main__":
    from time import time
    from sys import argv
    for churl in argv[1:]:
        s = time()
        download_ch_audio(churl)
        print("Time taken: {}s".format(int(time() - s)))
        