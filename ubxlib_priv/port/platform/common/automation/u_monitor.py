#!/usr/bin/env python

'''Monitor the running of a ubxlib example or test and report results.'''

import sys
import argparse
import re
import codecs
import queue
import threading
from time import time, ctime, sleep
from math import ceil
import subprocess
import serial                # Pyserial (make sure to do pip install pyserial)
import u_report
import u_utils

# Prefix to put at the start of all prints
PROMPT = "u_monitor"

# The connection types
CONNECTION_NONE = 0
CONNECTION_SERIAL = 1
CONNECTION_TELNET = 2
CONNECTION_PIPE = 3
CONNECTION_RTT = 4

def delayed_finish(*args):
    '''Function to set "finished" after a time delay'''

    # We will have been passed the "results" list as the
    # single entry in the args array.
    args[0]["finished"] = True

def reboot_callback(match, results, printer, prompt, reporter):
    '''Handler for reboots occuring unexpectedly'''
    del match

    printer.string("{}progress update - target has rebooted!".format(prompt))
    if reporter:
        reporter.event(u_report.EVENT_TYPE_TEST,
                       u_report.EVENT_ERROR,
                       "target has rebooted")
    results["reboots"] += 1
    # After one of these messages the target can often spit-out
    # useful information so wait a second or two before stopping
    # capture
    finish_timer = threading.Timer(2, delayed_finish, args=[results])
    finish_timer.start()

def run_callback(match, results, printer, prompt, reporter):
    '''Handler for an item beginning to run'''

    del reporter
    results["last_start_time"] = time()
    printer.string("{}progress update - item {}() started on {}.".     \
                   format(prompt, match.group(1), ctime(results["last_start_time"])))

    results["items_run"] += 1

def record_outcome(results, name, duration, status):
    '''What it says'''
    outcome = [name, duration, status]
    results["outcomes"].append(outcome)

def pass_callback(match, results, printer, prompt, reporter):
    '''Handler for an item passing'''

    end_time = time()
    duration = int(ceil(end_time - results["last_start_time"]))
    string = "{}() passed on {} after running for {:.0f} second(s)".  \
             format(match.group(1), ctime(end_time), duration)
    printer.string("{}progress update - item {}.".                               \
                   format(prompt, string))
    if reporter:
        reporter.event(u_report.EVENT_TYPE_TEST,
                       u_report.EVENT_PASSED,
                       string)
    record_outcome(results, match.group(1),
                   int(ceil(end_time - results["last_start_time"])), "PASS")

def fail_callback(match, results, printer, prompt, reporter):
    '''Handler for a test failing'''

    results["items_failed"] += 1
    end_time = time()
    string = "{}() FAILED on {} after running for {:.0f} second(s)".\
                   format(match.group(1), ctime(end_time),
                          ceil(end_time - results["last_start_time"]))
    printer.string("{}progress update - item {}.".format(prompt, string))
    if reporter:
        reporter.event(u_report.EVENT_TYPE_TEST,
                       u_report.EVENT_FAILED,
                       string)
    record_outcome(results, match.group(1),
                   int(ceil(end_time - results["last_start_time"])), "FAIL")

def finish_callback(match, results, printer, prompt, reporter):
    '''Handler for a run finishing'''

    end_time = time()
    duration_hours = int((end_time - results["overall_start_time"]) / 3600)
    duration_minutes = int(((end_time - results["overall_start_time"]) -
                            (duration_hours * 3600)) / 60)
    duration_seconds = int((end_time - results["overall_start_time"]) -
                           (duration_hours * 3600) - (duration_minutes * 60))
    results["items_run"] = int(match.group(1))
    results["items_failed"] = int(match.group(2))
    results["items_ignored"] = int(match.group(3))
    printer.string("{}run completed on {}, {} item(s) run, {} item(s) failed,"\
                   " {} item(s) ignored, run took {}:{:02d}:{:02d}.". \
                   format(prompt, ctime(end_time), results["items_run"],
                          results["items_failed"], results["items_ignored"],
                          duration_hours, duration_minutes, duration_seconds))
    if reporter:
        reporter.test_suite_completed_event(results["items_run"], results["items_failed"],
                                            results["items_ignored"],
                                            "run took {}:{:02d}:{:02d}".            \
                                            format(duration_hours, duration_minutes,
                                                   duration_seconds))
    results["finished"] = True

# List of regex strings to look for in each line returned by
# the test output and a function to call when the regex
# is matched.  The regex result is passed to the callback.
# Regex tested at https://regex101.com/ selecting Python as the flavour
INTERESTING = [[r"abort()", reboot_callback],
               # This one for ESP32 aborts
               [r"Guru Meditation Error", reboot_callback],
               # This one for NRF52 aborts
               [r"<error> hardfault", reboot_callback],
               # This one for Zephyr aborts
               [r">>> ZEPHYR FATAL ERROR", reboot_callback],
               # Match, for example "BLAH: Running getSetMnoProfile..." capturing the "getSetMnoProfile" part
               [r"(?:^.*Running) +([^\.]+(?=\.))...$", run_callback],
               # Match, for example "C:/temp/file.c:890:connectedThings:PASS" capturing the "connectThings" part
               [r"(?:^.*?(?:\.c:))(?:[0-9]*:)(.*?):PASS$", pass_callback],
               # Match, for example "C:/temp/file.c:900:tcpEchoAsync:FAIL:Function sock.  Expression Evaluated To FALSE" capturing the "connectThings" part
               [r"(?:^.*?(?:\.c:))(?:[0-9]*:)(.*?):FAIL:", fail_callback],
               # Match, for example "22 Tests 1 Failures 0 Ignored" capturing the numbers
               [r"(^[0-9]+) Test(?:s*) ([0-9]+) Failure(?:s*) ([0-9]+) Ignored", finish_callback]]

def readline_and_queue(results, read_queue, in_handle, connection_type, terminator):
    '''Read lines from the input and queue them'''
    while not results["finished"]:
        line = pwar_readline(in_handle, connection_type, terminator)
        if line:
            read_queue.put(line)
        # Let others in
        sleep(0.01)

# Read lines from input, returns the line as
# a string when terminator or '\n' is encountered.
# Does NOT return the terminating character
# If a read timeout occurs then None is returned.
def pwar_readline(in_handle, connection_type, terminator=None):
    '''Phil Ware's marvellous readline function'''
    return_value = None
    line = ""
    if terminator is None:
        terminator = "\n"
    if connection_type == CONNECTION_TELNET:
        terminator_bytes = bytes(terminator, 'ascii')
        # I was hoping that all sources of data
        # would have a read() function but it turns
        # out that Telnet does not, it has read_until()
        # which returns a whole line with a timeout
        # Note: deliberately don't handle the exception that
        # the Telnet port has been closed here, allow it
        # to stop us entirely
        # Long time-out as we don't want partial lines
        try:
            line = in_handle.read_until(terminator_bytes, 1).decode('ascii')
        except UnicodeDecodeError:
            # Just ignore it.
            pass
        if line != "":
            # To make this work the same way as the
            # serial and exe cases, need to remove the terminator
            # and remove any dangling \n left on the front
            line = line.rstrip(terminator)
            line = line.lstrip("\n")
        else:
            line = None
        return_value = line
        # Serial ports just use read()
    elif connection_type == CONNECTION_SERIAL or connection_type == CONNECTION_RTT:
        eol = False
        try:
            while not eol and line is not None:
                buf = in_handle.read(1)
                if buf:
                    character = buf.decode('ascii')
                    eol = character == terminator
                    if not eol:
                        line = line + character
                else:
                    line = None
                    # Since this is a busy/wait we sleep a bit if there is no data
                    # to offload the CPU
                    sleep(0.01)
            if eol:
                line = line.strip()
        except UnicodeDecodeError:
            # Just ignore it.
            pass
        return_value = line
        # For pipes, need to keep re-reading even
        # when nothing is there to avoid reading partial
        # lines as the pipe is being filled
    elif connection_type == CONNECTION_PIPE:
        start_time = time()
        eol = False
        try:
            while not eol and (time() - start_time < 5):
                buf = in_handle.read(1)
                if buf:
                    character = buf.decode('ascii')
                    eol = character == terminator
                    if not eol:
                        line = line + character
                else:
                    # Since this is a busy/wait we sleep a bit if there is no data
                    # to offload the CPU
                    sleep(0.01)
            if eol:
                line = line.strip()
        except UnicodeDecodeError:
            # Just ignore it.
            pass
        return_value = line

    if return_value == None or return_value == "":
        # Typically this function is called from a busy/wait loop
        # so if there currently no data available we sleep a bit
        # to offload the CPU
        sleep(0.01)

    return return_value

# Start the required executable.
def start_exe(exe_name, printer, prompt):
    '''Launch an executable as a sub-process'''
    return_value = None
    stdout_handle = None
    text = "{}trying to launch \"{}\" as an executable...".     \
           format(prompt, exe_name)
    try:
        popen_keywords = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
            'bufsize': 1,
            'shell': True # Jenkins hangs without this
        }
        return_value = subprocess.Popen(exe_name, **popen_keywords)
        stdout_handle = return_value.stdout
    except (ValueError, serial.SerialException, WindowsError):
        printer.string("{} failed.".format(text))
    return return_value, stdout_handle

# Send the given string before running, only used on ESP32 platforms.
def esp32_send_first(send_string, in_handle, connection_type, printer, prompt):
    '''Send a string before running tests, used on ESP32 platforms'''
    success = False
    try:
        line = ""
        # Read the opening splurge from the target
        # if there is any
        printer.string("{}reading initial text from input...".\
                       format(prompt))
        sleep(1)
        # Wait for the test selection prompt
        while line is not None and \
              line.find("Press ENTER to see the list of tests.") < 0:
            line = pwar_readline(in_handle, connection_type, "\r")
            if line is not None:
                printer.string("{}{}".format(prompt, line))
        # For debug purposes, send a newline to the unit
        # test app to get it to list the tests
        printer.string("{}listing items...".format(prompt))
        in_handle.write("\r\n".encode("ascii"))
        line = ""
        while line is not None:
            line = pwar_readline(in_handle, connection_type, "\r")
            if line is not None:
                printer.string("{}{}".format(prompt, line))
        # Now send the string
        printer.string("{}sending {}".format(prompt, send_string))
        in_handle.write(send_string.encode("ascii"))
        in_handle.write("\r\n".encode("ascii"))
        printer.string("{}run started on {}.".format(prompt, ctime(time())))
        success = True
    except serial.SerialException as ex:
        printer.string("{}{} while accessing port {}: {}.".
                       format(prompt, type(ex).__name__,
                              in_handle.name, str(ex)))
    return success

# Watch the output from the items being run
# looking for INTERESTING things.
def watch_items(in_handle, connection_type, results, guard_time_seconds,
                inactivity_time_seconds, terminator, printer,
                reporter, prompt, keep_going_flag):
    '''Watch output'''
    return_value = -1
    start_time = time()
    last_activity_time = time()

    printer.string("{}watching output until run completes...".format(prompt))

    # Start a thread to read lines from in_handle
    # This is done in a separate thread as it can block or
    # hang; this way we get to detect that and time out.
    read_queue = queue.Queue()
    readline_thread = threading.Thread(target=readline_and_queue,
                                       args=(results, read_queue, in_handle,
                                             connection_type, terminator))
    readline_thread.start()

    try:
        while u_utils.keep_going(keep_going_flag, printer, prompt) and \
              not results["finished"] and                              \
              (not guard_time_seconds or                               \
               (time() - start_time < guard_time_seconds)) and         \
              (not inactivity_time_seconds or                          \
               (time() - last_activity_time < inactivity_time_seconds)):
            try:
                line = read_queue.get(timeout=0.5)
                last_activity_time = time()
                printer.string("{}{}".format(prompt, line), file_only=True)
                for entry in INTERESTING:
                    match = re.match(entry[0], line)
                    if match:
                        entry[1](match, results, printer, prompt, reporter)
            except queue.Empty:
                pass
            # Let others in
            sleep(0.01)
        # Set this to stop the read thread
        results["finished"] = True
        readline_thread.join()
        if guard_time_seconds and (time() - start_time >= guard_time_seconds):
            printer.string("{}guard timer ({} second(s))"        \
                           "  expired.".format(prompt, guard_time_seconds))
        elif inactivity_time_seconds and (time() - last_activity_time >= inactivity_time_seconds):
            printer.string("{}inactivity timer ({} second(s))"   \
                           " expired.".format(prompt, inactivity_time_seconds))
        else:
            return_value = results["items_failed"] + results["reboots"]
    except (serial.SerialException, EOFError) as ex:
        printer.string("{}{} while accessing port {}: {}.".
                       format(prompt, type(ex).__name__,
                              in_handle.name, str(ex)))

    return return_value

def main(connection_handle, connection_type, guard_time_seconds,
         inactivity_time_seconds, terminator, instance, printer,
         reporter, test_report_handle, send_string=None,
         keep_going_flag=None):
    '''Main as a function'''
    # Dictionary in which results are stored
    results = {"finished": False,
               "reboots": 0, "items_run": 0,
               "items_failed": 0, "items_ignored": 0,
               "overall_start_time": 0, "last_start_time": 0,
               "outcomes": []}
    results["last_start_time"] = time()
    return_value = -1

    if instance:
        prompt = PROMPT + "_" + u_utils.get_instance_text(instance) + ": "
    else:
        prompt = PROMPT + ": "

    # If we have a serial interface we have can chose which tests to run
    # (at least, on the ESP32 platform) else the lot will just run
    if (send_string is None or esp32_send_first(send_string, connection_handle,
                                                connection_type, printer, prompt)):
        results["overall_start_time"] = time()
        return_value = watch_items(connection_handle, connection_type, results,
                                   guard_time_seconds, inactivity_time_seconds,
                                   terminator, printer, reporter, prompt,
                                   keep_going_flag)

    # Write the report
    if test_report_handle and instance:
        printer.string("{}writing report file...".format(prompt))
        test_report_handle.write("<testsuite name=\"{}\" tests=\"{}\" failures=\"{}\">\n". \
                                 format("instance " + u_utils.get_instance_text(instance),
                                        results["items_run"],
                                        results["items_failed"]))
        for outcome in results["outcomes"]:
            test_report_handle.write("    <testcase classname=\"{}\" name=\"{}\" " \
                                     "time=\"{}\" status=\"{}\"></testcase>\n".    \
                                     format("ubxlib_tests", outcome[0], outcome[1],
                                            outcome[2]))
        test_report_handle.write("</testsuite>\n")

    printer.string("{}end with return value {}.".format(prompt, return_value))

    return return_value

if __name__ == "__main__":
    SUCCESS = True
    PROCESS_HANDLE = None
    RETURN_VALUE = -1
    LOG_HANDLE = None
    TEST_REPORT_HANDLE = None
    CONNECTION_TYPE = CONNECTION_NONE

    PARSER = argparse.ArgumentParser(description="A script to"    \
                                     " run tests/examples and"    \
                                     " detect the outcome, communicating" \
                                     " with the target running"   \
                                     " the build.  Return value"  \
                                     " is zero on success"        \
                                     " negative on unable to run" \
                                     " positive indicating number"\
                                     " of failed test cases")
    PARSER.add_argument("port", help="the source of data: either the"   \
                        " COM port on which the build is communicating," \
                        " e.g. COM1 (baud rate fixed at 115,200)" \
                        " or a port number (in which case a Telnet" \
                        " session is opened on localhost to grab the" \
                        " output) or an executable to run which should" \
                        " spew  the output from the unit test.")
    PARSER.add_argument("-s", help="send the given string to the"
                        " target before starting monitoring.  This"
                        " is only supported on the ESP32 platform"
                        " where the interface is a serial port; it"
                        " can be used to filter which items are"
                        " to be run.")
    PARSER.add_argument("-t", type=int, help="set a guard timer in seconds; if"
                        " the guard time expires this script will"
                        " stop and return a negative value.")
    PARSER.add_argument("-i", type=int, help="set an inactivity timer in seconds;"
                        " if the target emits nothing for this many"
                        " seconds this script will stop and return"
                        " a negative value.")
    PARSER.add_argument("-l", help="the file name to write the output to;" \
                        " any existing file will be overwritten.")
    PARSER.add_argument("-x", help="the file name to write an XML-format" \
                        " report to; any existing file will be overwritten.")
    ARGS = PARSER.parse_args()

    # The following line works around weird encoding problems where Python
    # doesn't like code page 65001 character encoding which Windows does
    # See https://stackoverflow.com/questions/878972/windows-cmd-encoding-change-causes-python-crash
    codecs.register(lambda name: codecs.lookup('utf-8') if name == 'cp65001' else None)

    # Open the log file
    if ARGS.l:
        LOG_HANDLE = open(ARGS.l, "w")
        if LOG_HANDLE:
            print("{}: writing log output to \"{}\".".format(PROMPT, ARGS.l))
        else:
            SUCCESS = False
            print("{}: unable to open log file \"{}\" for writing.".
                  format(PROMPT, ARGS.l))
    if SUCCESS:
        # Set up a printer, with a None queue
        # since we're only running one instance
        # from here
        PRINTER = u_utils.PrintToQueue(None, LOG_HANDLE)

        # Make the connection
        CONNECTION_TYPE = CONNECTION_SERIAL
        CONNECTION_HANDLE = u_utils.open_serial(ARGS.port, 115200, PRINTER, PROMPT)
        if CONNECTION_HANDLE is None:
            CONNECTION_TYPE = CONNECTION_TELNET
            CONNECTION_HANDLE = u_utils.open_telnet(ARGS.port, PRINTER, PROMPT)
        if CONNECTION_HANDLE is None:
            CONNECTION_TYPE = CONNECTION_PIPE
            PROCESS_HANDLE, CONNECTION_HANDLE = start_exe(ARGS.port, PRINTER, PROMPT)
        if CONNECTION_HANDLE is not None:
            # Open the report file
            if ARGS.x:
                TEST_REPORT_HANDLE = open(ARGS.x, "w")
                if TEST_REPORT_HANDLE:
                    print("{}: writing test report to \"{}\".".format(PROMPT, ARGS.x))
                else:
                    SUCCESS = False
                    print("{}: unable to open test report file \"{}\" for writing.".
                          format(PROMPT, ARGS.x))
            if SUCCESS:
                # Run things
                RETURN_VALUE = main(CONNECTION_HANDLE, CONNECTION_TYPE, ARGS.t,
                                    ARGS.i, "\r", None, PRINTER, None,
                                    TEST_REPORT_HANDLE, send_string=ARGS.s)

            # Tidy up
            if TEST_REPORT_HANDLE:
                TEST_REPORT_HANDLE.close()
            if LOG_HANDLE:
                LOG_HANDLE.close()
            if CONNECTION_TYPE == CONNECTION_PIPE:
                PROCESS_HANDLE.terminate()
            else:
                CONNECTION_HANDLE.close()

    sys.exit(RETURN_VALUE)
