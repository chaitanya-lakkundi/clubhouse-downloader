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

db = None
stats = None
stats_model = None


def commit(msg=""):
    global db, stats

    db.session.add(stats)
    try:
        db.session.commit()
    except Exception as e:
        print("Error while committing. ", msg, "\n\n", repr(e))
        db.session.rollback()


def get_chunk_urls(churl, only_info=False):
    from os import mkdir

    global db, stats

    print("Get chunk urls from ", churl)
    stats.stage += 1
    options = webdriver.ChromeOptions()
    options.add_argument("headless")
    driver = webdriver.Chrome(executable_path="./chromedriver", options=options)
    # driver = webdriver.Chrome(service=Service("./chromedriver"), options=options)
    driver.execute_cdp_cmd(
        "Network.setBlockedURLs",
        {
            "urls": [
                "https://www.clubhouse.com/__log",
                "https://www.googletagmanager.com/*",
                "https://www.google-analytics.com/*",
            ]
        },
    )
    driver.execute_cdp_cmd("Network.enable", {})

    driver.implicitly_wait(5)
    driver.get(churl)
    salt = str(uuid1()).split("-")[0][:5]
    chuid = churl.split("?")[0].split("/")[-1]
    chdir = chuid + "_" + salt
    print("CH directory: ", chdir)
    stats.chdir = chdir

    try:
        mkdir(chdir)
    except Exception as e:
        print("Unable to make directory: ", repr(e))
        stats.status = 2
        stats.msg = "Unable to make directory"
        commit()
        return

    commit()

    wait = WebDriverWait(driver, 10)
    try:
        click_to_play = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".rounded-room p"))
        )
        click_to_play.click()
    except Exception as e:
        print("Error in click_to_play: ", repr(e))
        stats.msg = "Error in click_to_play"

    room_name = driver.find_element(
        by=By.CSS_SELECTOR, value="#react-container h1"
    ).text
    try:
        title = driver.find_element(
            by=By.CSS_SELECTOR, value="#react-container h1:nth-child(2)"
        ).text
    except:
        title = ""

    try:
        audio = wait.until(EC.visibility_of_element_located((By.TAG_NAME, "audio")))
        sleep(2)
        duration = int(float(audio.get_attribute("duration")))
    except Exception as e:
        print("Error in finding audio element: ", repr(e))
        return

    stats.title = title
    stats.room = room_name
    stats.duration = duration
    commit()

    if only_info:
        driver.close()
        info = {"title": title, "room_name": room_name, "duration": duration}
        # TODO: returning different signature here. fix.
        return info

    driver.execute_script("arguments[0].muted = true", audio)

    currentTime = 0

    # if the script fails due to some reason, do not loop indefinitely. limit to 7200.
    while currentTime < duration and currentTime < 7200:
        pc = int(100 * currentTime / duration)
        print("{} %".format(pc))
        sleep(3)
        driver.execute_script(
            "arguments[0].currentTime = arguments[1]", audio, currentTime
        )
        currentTime += 29
        if currentTime % 5 * 29 == 0:
            stats.pc = pc
            stats.msg = "Scanning audio"
            commit()

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

    global db, stats
    stats.stage += 1
    resumeFrom = 0

    for en, c in enumerate(urls):
        fn = str(en + 1) + ".ts"
        try:
            open(path_join(destdir, fn), "rb").close()
        except:
            resumeFrom = en
            break

    done = 0
    err = 0
    for en, c in enumerate(urls):
        fn = str(en + 1) + ".ts"

        if en < resumeFrom:
            print("Skip ", fn)
            done += 1
            continue

        try:
            msg = "Downloading URL {}/{}".format(en + 1, len(urls))
            print(msg)
            urlretrieve(c, path_join(destdir, fn))
            done += 1
            if done % 5 == 0:
                stats.pc = int(100 * (en + 1) / len(urls))
                stats.msg = msg
                commit()

        except Exception as e:
            err += 1
            print(repr(e))
            stats.status = 2
            stats.msg = "Error in download_urls"
            commit()
            if err >= 4:
                break
    return done


def merge_chunks(chdir):
    from os.path import basename

    global db, stats

    stats.stage += 1
    msg = "Merge chunks in " + chdir
    stats.msg = msg
    commit()
    print(msg)

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
    from subprocess import run

    global db, stats

    stats.stage += 1
    print("Convert {} to {}".format(filepath, outpath))
    try:
        ffp = run(["ffmpeg", "-i", filepath, outpath], check=True)
    except Exception as e:
        print("Error in convert_to_m4a: ", repr(e))


def write_info_verify(filepath, info):
    from os.path import basename
    from mutagen.mp4 import MP4

    global db, stats

    stats.stage += 1

    # TODO: add title, room name, date in tags (attributes)
    aud = MP4(filepath)
    basepath = filepath[: -len(basename(filepath))]

    with open(path_join(basepath, "info"), "w") as fd:
        fd.write("title: " + info["title"] + "\n")
        fd.write("room: " + info["room_name"] + "\n")
        fd.write("duration: " + str(round(aud.info.length, 2)) + "\n")
        fd.write("fileinfo: " + aud.pprint() + "\n")

    durdiff = abs(info["duration"] - round(aud.info.length, 2))
    # decimals can be ignored. but all the chunks have to be present
    if durdiff < 1:
        open(path_join(basepath, "success"), "w").close()
        stats.pc = 100
        stats.msg = "Success"
        stats.status = 1
        commit()
        return True
    else:
        msg = "Difference in duration is " + str(durdiff)
        stats.pc = 100
        stats.msg = msg
        stats.status = 2
        commit()
        print(msg)
        return False


def cleanup(chdir):
    from os import remove, symlink
    from os.path import exists

    global stats

    print("Cleanup ", chdir)

    if not exists(path_join(chdir, "success")):
        return

    for fn in glob(path_join(chdir, "*.ts")):
        try:
            remove(fn)
        except Exception as e:
            print(repr(e))

    # add symlink to download
    sln = str(uuid1()).split("-")[0] + ".m4a"
    sln_path = "static{0}media{0}{1}".format(sep, sln)
    # TODO: do not hard code path
    symlink("../../" + path_join(chdir, "out.m4a"), sln_path)
    stats.sln = sln
    commit()


def download_ch_audio(churl, db_conn=None, db_inst=None, db_model=None):
    from time import time
    from os.path import exists

    global db, stats, stats_model

    db = db_conn
    stats = db_inst
    stats_model = db_model

    rid = churl.split("/")[-1]

    get_chunk_urls_flag = True
    download_urls_flag = True
    merge_chunks_flag = True
    convert_to_m4a_flag = True
    write_info_verify_flag = True
    candidate_chdir = {}
    chdir = None

    for td in glob(rid + "*"):
        # temp dir
        try:
            with open(path_join(td, "chunks"), "r") as fd:
                candidate_chdir[4] = td
                get_chunk_urls_flag = False
                # file count to expect
                efc = len(fd.read().splitlines())
            chunkf_list = glob(path_join(td, "*.ts"))
            # actual file count
            afc = len(chunkf_list)

            if afc >= efc:
                count = afc
                candidate_chdir[3] = td
                download_urls_flag = False

            if exists(path_join(td, "out.ts")):
                candidate_chdir[2] = td
                merge_chunks_flag = False

            if exists(path_join(td, "out.m4a")):
                candidate_chdir[1] = td
                convert_to_m4a_flag = False

            if exists(path_join(td, "success")):
                candidate_chdir[0] = td
                write_info_verify_flag = False
                # short circuit if success is present
                # TODO: handle gracefully
                chdir = td
                stats = stats_model.query.filter_by(chdir=chdir).first()
                cleanup(td)
                return

        except Exception as e:
            print(repr(e))

    print("Candidates = ", candidate_chdir)

    for i in range(5):
        try:
            chdir = candidate_chdir[i]
            break
        except:
            pass

    try:
        tmp_stats = stats_model.query.filter_by(chdir=chdir).first()
        if tmp_stats:
            stats = tmp_stats
        # need to free memory of db_inst
        info = {
            "title": stats.title,
            "room_name": stats.room,
            "duration": stats.duration,
        }
        if not stats.title or not stats.room or not stats.duration:
            raise Exception("Info not found")
    except UnboundLocalError:
        # chdir is undefined yet
        pass
    except:        
        # this exception occurs when the database does not contain info of some existing folder
        if not get_chunk_urls_flag:
            info = get_chunk_urls(churl, only_info=True)

    if not get_chunk_urls_flag:
        with open(path_join(chdir, "chunks"), "r") as fd:
            chunks = fd.read().splitlines()
            count = len(chunks)

    s = time()
    try:
        if get_chunk_urls_flag:
            chunks, chdir, info = get_chunk_urls(churl)

        if download_urls_flag:
            count = download_urls(chunks, chdir)
            if len(chunks) != count:
                # time may be expired for urls
                chunks, chdir, info = get_chunk_urls(churl)
                count = download_urls(chunks, chdir)

    except Exception as e:
        print("Error in download_ch_audio: ", repr(e))
        return

    if len(chunks) != count:
        print("Some chunks have not been downloaded")

    if merge_chunks_flag:
        fn = merge_chunks(chdir)
    else:
        fn = path_join(chdir, "out.ts")

    if convert_to_m4a_flag:
        convert_to_m4a(fn, path_join(chdir, "out.m4a"))

    if write_info_verify_flag:
        if write_info_verify(path_join(chdir, "out.m4a"), info):
            print("Success on ", churl)
        else:
            print("Failure on ", churl)
        msg = "Time taken: {}s".format(int(time() - s))
        print(msg)
        stats.msg = msg
        stats.time_elapsed = int(time() - s)
        commit()

    cleanup(chdir)


if __name__ == "__main__":
    from sys import argv

    for churl in argv[1:]:
        download_ch_audio(churl)
