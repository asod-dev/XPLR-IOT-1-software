#!/usr/bin/env python

'''Build/run ubxlib for Zephyr and report results.'''

import os                    # For sep(), getcwd(), listdir()
from time import time, sleep
import u_connection
import u_monitor
import u_report
import u_utils
import u_settings
from u_rtt_reader import URttReader

# Prefix to put at the start of all prints
PROMPT = "u_run_zephyr_"

# Expected location of nRFConnect installation
NRFCONNECT_PATH = u_settings.ZEPHYR_NRFCONNECT_PATH # e.g. "C:\\nrfconnect\\v1.4.2"

# The list of things to execute jlink.exe
RUN_JLINK = [u_utils.JLINK_PATH] + u_settings.ZEPHYR_RUN_JLINK #

# Nordic nrfjprog CLI command
NRFJPROG = "nrfjprog{}".format(u_utils.EXE_EXT)

# List of device types we support as known to JLink
JLINK_DEVICE = ["nRF52833_XXAA", "nRF52840_XXAA", "nRF5340_XXAA_APP"]

# JLink needs to be treated with kid gloves concerning shutting it down
JLINK_EXIT_DELAY_SECONDS = u_settings.JLINK_EXIT_DELAY_SECONDS # e.g. 10

# The path to the Zephyr batch file that sets up its
# environment variables
ZEPHYR_ENV_CMD = u_settings.ZEPHYR_ZEPHYR_ENV_CMD # e.g. NRFCONNECT_PATH + os.sep + "zephyr\\zephyr-env.cmd"

# The path to the git-cmd batch file that sets up the
# git-bash environment variables
GIT_BASH_ENV_CMD = u_settings.ZEPHYR_GIT_BASH_ENV_CMD # e.g. NRFCONNECT_PATH + os.sep + "toolchain\\cmd\\env.cmd"

# The directory where the runner build can be found
RUNNER_DIR = u_settings.ZEPHYR_DIR + os.sep + "runner"

# The name of the output sub-directory
BUILD_SUBDIR = u_settings.ZEPHYR_BUILD_SUBDIR # e.g. "build"

# The guard time for this build in seconds,
# noting that it can be quite long when
# many builds are running in parallel.
BUILD_GUARD_TIME_SECONDS = u_settings.ZEPHYR_BUILD_GUARD_TIME_SECONDS # e.g. 60 * 30

# The guard time waiting for a lock on the HW connection seconds
CONNECTION_LOCK_GUARD_TIME_SECONDS = u_connection.CONNECTION_LOCK_GUARD_TIME_SECONDS

# The guard time waiting for a install lock in seconds
INSTALL_LOCK_WAIT_SECONDS = u_utils.INSTALL_LOCK_WAIT_SECONDS

# The download guard time for this build in seconds
DOWNLOAD_GUARD_TIME_SECONDS = u_utils.DOWNLOAD_GUARD_TIME_SECONDS

# The guard time for running tests in seconds
RUN_GUARD_TIME_SECONDS = u_utils.RUN_GUARD_TIME_SECONDS

# The inactivity time for running tests in seconds
RUN_INACTIVITY_TIME_SECONDS = u_utils.RUN_INACTIVITY_TIME_SECONDS

# Table of "where.exe" search paths for tools required to be installed
# plus hints as to how to install the tools and how to read their version
TOOLS_LIST = [{"which_string": "west",
               "hint": "can't find \"west\", the Zephyr build tool"  \
                       " (actually a Python script), please install" \
                       " it by opening a command window with "       \
                       " administrator privileges and then typing:"  \
                       " \"pip install west\" followed by something" \
                       " like: \"pip install -r C:\\nrfconnect"      \
                       "\\v1.4.2\\zephyr\\scripts\\requirements.txt\".",
               "version_switch": "--version"},
              {"which_string": NRFJPROG,
               "hint": "couldn't find the nRFConnect SDK at NRFCONNECT_PATH,"  \
                       " please download the latest version from"              \
                       " https://www.nordicsemi.com/Software-and-Tools/"       \
                       "Development-Tools/nRF-Connect-for-desktop"             \
                       " or override the environment variable NRFCONNECT_PATH" \
                       " to reflect where it is.",
               "version_switch": "--version"},
              {"which_string": u_utils.JLINK_PATH,
               "hint": "can't find the SEGGER tools, please install"         \
                       " the latest version of their JLink tools from"       \
                       " https://www.segger.com/downloads/jlink/JLink_Windows.exe" \
                       " and add them to the path.",
               "version_switch": None}]

def print_env(returned_env, printer, prompt):
    '''Print a dictionary that contains the new environment'''
    printer.string("{}environment will be:".format(prompt))
    if returned_env:
        for key, value in returned_env.items():
            printer.string("{}{}={}".format(prompt, key, value))
    else:
        printer.string("{}EMPTY".format(prompt))

def check_installation(tools_list, printer, prompt):
    '''Check that everything required has been installed'''
    success = True

    # Check for the tools on the path
    printer.string("{}checking tools...".format(prompt))
    for item in tools_list:
        if u_utils.exe_where(item["which_string"], item["hint"],
                             printer, prompt):
            if item["version_switch"]:
                u_utils.exe_version(item["which_string"],
                                    item["version_switch"],
                                    printer, prompt)
        else:
            success = False

    return success

def set_env(printer, prompt):
    '''Run the batch files that set up the environment variables'''
    returned_env = {}
    returned_env1 = {}
    returned_env2 = {}
    count = 0

    # It is possible for the process of extracting
    # the environment variables to fail due to machine
    # loading (see comments against EXE_RUN_QUEUE_WAIT_SECONDS
    # in exe_run) so give this up to three chances to succeed
    while not returned_env1 and (count < 3):
        # set shell to True to keep Jenkins happy
        u_utils.exe_run(u_utils.split_command_line_args(ZEPHYR_ENV_CMD), None,
                        printer, prompt, shell_cmd=True,
                        returned_env=returned_env1)
        if not returned_env1:
            printer.string("{}warning: retrying {} to capture"  \
                           " the environment variables...".
                           format(prompt, ZEPHYR_ENV_CMD))
        count += 1
    count = 0
    if returned_env1:
        while not returned_env2 and (count < 3):
            # set shell to True to keep Jenkins happy
            u_utils.exe_run(u_utils.split_command_line_args(GIT_BASH_ENV_CMD), None,
                            printer, prompt, shell_cmd=True,
                            returned_env=returned_env2)
            if not returned_env2:
                printer.string("{}warning: retrying {} to capture"  \
                               " the environment variables...".
                               format(prompt, GIT_BASH_ENV_CMD))
            count += 1
        if returned_env2:
            returned_env = {**returned_env1, **returned_env2}

    return returned_env

def jlink_device(mcu):
    '''Return the JLink device name for a given MCU'''
    jlink_device_name = None

    # The bit before the underscore in a JLink device name
    # is always the MCU name so we can do a match for just
    # that bit against the MCU name we are given
    for device in JLINK_DEVICE:
        if device.split("_")[0].lower() == mcu.lower():
            jlink_device_name = device
            break

    return jlink_device_name

def print_call_list(call_list, printer, prompt):
    '''Print the call list'''
    tmp = ""
    for item in call_list:
        tmp += " " + item
    printer.string("{}in directory {} calling{}".         \
                   format(prompt, os.getcwd(), tmp))

def download_single_cpu(connection, jlink_device_name, guard_time_seconds, build_dir, env, printer, prompt):
    '''Assemble the call list'''
    # Note that we use JLink to do the download
    # rather than the default of nrfjprog since there
    # appears to be no way to prevent nrfjprog from
    # resetting the target after the download when
    # it is used under west (whereas when JLink is
    # used this is the default)
    call_list = ["west", "flash", "-d", build_dir, "--runner", "jlink",
                     "--erase", "--no-reset-after-load"]
    tool_opt = "-Autoconnect 1 -ExitOnError 1 -NoGui 1"

    if jlink_device_name:
        call_list.extend(["--device", jlink_device_name])
    # Add the options that have to go through "--tool-opt"
    if connection and "debugger" in connection and connection["debugger"]:
        tool_opt += " -USB " + connection["debugger"]
    if tool_opt:
        call_list.extend(["--tool-opt", tool_opt])

    print_call_list(call_list, printer, prompt)

    # Call it
    return u_utils.exe_run(call_list, guard_time_seconds, printer, prompt,
                           shell_cmd=True, set_env=env)

def download_nrf53(connection, guard_time_seconds, build_dir, env, printer, prompt):
    '''Download the given hex file(s) on NRF53'''
    cpunet_hex_path = os.path.join(build_dir, "hci_rpmsg", "zephyr", "merged_CPUNET.hex")
    success = True
    nrfjprog_cmd = [NRFJPROG, "-f", "NRF53"]
    if connection and "debugger" in connection and connection["debugger"]:
        nrfjprog_cmd.extend(["-s", connection["debugger"]])

    # Disable read protection first
    if os.path.exists(cpunet_hex_path):
        printer.string("{}---- recover NETCPU ----".format(prompt))

        call_list = nrfjprog_cmd + ["--coprocessor", "CP_NETWORK", "--recover"]
        print_call_list(call_list, printer, prompt)
        success = u_utils.exe_run(call_list, guard_time_seconds, printer,
                                  prompt, shell_cmd=True, set_env=env)

    if success:
        # Give nrfjprog some time to relax
        sleep(1)
        printer.string("{}--- recover APP ----".format(prompt))
        call_list = nrfjprog_cmd + ["--coprocessor", "CP_APPLICATION", "--recover"]
        print_call_list(call_list, printer, prompt)
        success = u_utils.exe_run(call_list, guard_time_seconds, printer,
                                  prompt, shell_cmd=True, set_env=env)


    if success and os.path.exists(cpunet_hex_path):
        # Now flash network core
        # Give nrfjprog some time to relax
        sleep(1)
        printer.string("{}---- download NETCPU ----".format(prompt))
        call_list = nrfjprog_cmd + ["--coprocessor", "CP_NETWORK", "--chiperase", "--program", cpunet_hex_path]
        print_call_list(call_list, printer, prompt)
        success = u_utils.exe_run(call_list, guard_time_seconds, printer,
                                  prompt, shell_cmd=True, set_env=env)

    if success:
        # Give nrfjprog some time to relax
        sleep(1)
        app_hex_path = os.path.join(build_dir, "zephyr", "merged.hex")
        printer.string("{}---- download APP ----".format(prompt))

        call_list = nrfjprog_cmd + ["--coprocessor", "CP_APPLICATION", "--chiperase", "--program", app_hex_path]
        print_call_list(call_list, printer, prompt)
        success = u_utils.exe_run(call_list, guard_time_seconds, printer,
                                  prompt, shell_cmd=True, set_env=env)

    return success

def download(connection, jlink_device_name, guard_time_seconds,
             build_dir, env, printer, prompt):
    '''Download the given hex file(s)'''
    if jlink_device_name == "nRF5340_XXAA_APP":
        success = download_nrf53(connection, guard_time_seconds,
                                 build_dir, env, printer, prompt)
    else:
        success = download_single_cpu(connection, jlink_device_name, guard_time_seconds,
                                      build_dir, env, printer, prompt)
    return success

def build(board, clean, ubxlib_dir, defines, env, printer, prompt, reporter, keep_going_flag):
    '''Build using west'''
    call_list = []
    defines_text = ""
    runner_dir = ubxlib_dir + os.sep + RUNNER_DIR
    output_dir = os.getcwd() + os.sep + BUILD_SUBDIR
    build_dir = None

    # Put west at the front of the call list
    call_list.append("west")

    # Make it verbose
    call_list.append("-v")
    # Do a build
    call_list.append("build")
    # Pick up .overlay and .conf files automatically
    call_list.append("-p")
    call_list.append("auto")
    # Board name
    call_list.append("-b")
    call_list.append((board).replace("\\", "/"))
    # Build products directory
    call_list.append("-d")
    call_list.append((BUILD_SUBDIR).replace("\\", "/"))
    if clean:
        # Clean
        call_list.append("-p")
        call_list.append("always")
    # Now the path to build
    call_list.append((runner_dir).replace("\\", "/"))
    call_list.append("-DZEPHYR_EXTRA_MODULES=" + ubxlib_dir)

    # CCACHE is a pain in the bum: falls over on Windows
    # path length issues randomly and doesn't say where.
    # Since we're generally doing clean builds, disable it
    env["CCACHE_DISABLE"] = "1"

    if defines:
        # Set up the U_FLAGS environment variables
        for idx, define in enumerate(defines):
            if idx == 0:
                defines_text += "-D" + define
            else:
                defines_text += " -D" + define
        printer.string("{}setting environment variables U_FLAGS={}".
                       format(prompt, defines_text))
        env["U_FLAGS"] = defines_text

    # Clear the output folder ourselves as well, just
    # to be completely sure
    if not clean or u_utils.deltree(BUILD_SUBDIR, printer, prompt):
        # Print what we're gonna do
        tmp = ""
        for item in call_list:
            tmp += " " + item
        printer.string("{}in directory {} calling{}".         \
                       format(prompt, os.getcwd(), tmp))

        # Call west to do the build
        # Set shell to keep Jenkins happy
        if u_utils.exe_run(call_list, BUILD_GUARD_TIME_SECONDS,
                           printer, prompt, shell_cmd=True,
                           set_env=env, keep_going_flag=keep_going_flag):
            build_dir = output_dir
    else:
        reporter.event(u_report.EVENT_TYPE_BUILD,
                       u_report.EVENT_ERROR,
                       "unable to clean build directory")

    return build_dir

def run(instance, mcu, board, toolchain, connection, connection_lock,
        platform_lock, misc_locks, clean, defines, ubxlib_dir,
        working_dir, printer, reporter, test_report_handle,
        keep_going_flag=None):
    '''Build/run on Zephyr'''
    return_value = -1
    build_dir = None
    instance_text = u_utils.get_instance_text(instance)

    # Don't need the platform or misc locks
    del platform_lock
    del misc_locks

    # Only one toolchain for Zephyr
    del toolchain

    prompt = PROMPT + instance_text + ": "

    # Print out what we've been told to do
    text = "running Zephyr for " + mcu + " (on a \"" + board + "\" board)"
    if connection and "debugger" in connection and connection["debugger"]:
        text += ", on JLink debugger serial number " + connection["debugger"]
    if clean:
        text += ", clean build"
    if defines:
        text += ", with #define(s)"
        for idx, define in enumerate(defines):
            if idx == 0:
                text += " \"" + define + "\""
            else:
                text += ", \"" + define + "\""
    if ubxlib_dir:
        text += ", ubxlib directory \"" + ubxlib_dir + "\""
    if working_dir:
        text += ", working directory \"" + working_dir + "\""
    printer.string("{}{}.".format(prompt, text))

    reporter.event(u_report.EVENT_TYPE_BUILD,
                   u_report.EVENT_START,
                   "Zephyr")
    # Switch to the working directory
    with u_utils.ChangeDir(working_dir):
        # Check that everything we need is installed
        # and configured
        if u_utils.keep_going(keep_going_flag, printer, prompt) and \
           check_installation(TOOLS_LIST, printer, prompt):
            # Set up the environment variables for Zephyr
            returned_env = set_env(printer, prompt)
            if u_utils.keep_going(keep_going_flag, printer, prompt) and \
               returned_env:
                # The west tools need to use the environment
                # configured above.
                print_env(returned_env, printer, prompt)
                # Note that Zephyr brings in its own
                # copy of Unity so there is no need to
                # fetch it here.
                if board:
                    # Do the build
                    build_start_time = time()
                    build_dir = build(board, clean, ubxlib_dir, defines,
                                      returned_env, printer, prompt, reporter,
                                      keep_going_flag)
                    if u_utils.keep_going(keep_going_flag, printer, prompt) and \
                       build_dir:
                        # Build succeeded, need to lock some things to do the download
                        reporter.event(u_report.EVENT_TYPE_BUILD,
                                       u_report.EVENT_PASSED,
                                       "build took {:.0f} second(s)".format(time() -
                                                                            build_start_time))
                        # Do the download
                        with u_connection.Lock(connection, connection_lock,
                                               CONNECTION_LOCK_GUARD_TIME_SECONDS,
                                               printer, prompt,
                                               keep_going_flag) as locked_connection:
                            if locked_connection:
                                # Get the device name for JLink
                                jlink_device_name = jlink_device(mcu)
                                if not jlink_device_name:
                                    reporter.event(u_report.EVENT_TYPE_INFRASTRUCTURE,
                                                   u_report.EVENT_WARNING,
                                                   "MCU not found in JLink devices")
                                # Do the download
                                reporter.event(u_report.EVENT_TYPE_DOWNLOAD,
                                               u_report.EVENT_START)
                                retries = 0
                                downloaded = False
                                while u_utils.keep_going(keep_going_flag, printer, prompt) and \
                                      not downloaded and (retries < 3):
                                    downloaded = download(connection, jlink_device_name,
                                                          DOWNLOAD_GUARD_TIME_SECONDS,
                                                          build_dir, returned_env, printer, prompt)
                                    if not downloaded:
                                        reporter.event(u_report.EVENT_TYPE_DOWNLOAD,
                                                       u_report.EVENT_WARNING,
                                                       "unable to download, will retry...")
                                        retries += 1
                                        sleep(5)
                                if downloaded:
                                    reporter.event(u_report.EVENT_TYPE_DOWNLOAD,
                                                   u_report.EVENT_COMPLETE)
                                    # Now the target can be reset
                                    u_utils.reset_nrf_target(connection,
                                                             printer, prompt)
                                    reporter.event(u_report.EVENT_TYPE_TEST,
                                                   u_report.EVENT_START)

                                    with URttReader(jlink_device(mcu),
                                                    jlink_serial=connection["debugger"],
                                                    printer=printer,
                                                    prompt=prompt) as rtt_reader:
                                        return_value = u_monitor.main(rtt_reader,
                                                                      u_monitor.CONNECTION_RTT,
                                                                      RUN_GUARD_TIME_SECONDS,
                                                                      RUN_INACTIVITY_TIME_SECONDS,
                                                                      "\n", instance, printer,
                                                                      reporter,
                                                                      test_report_handle,
                                                                      keep_going_flag=keep_going_flag)
                                    if return_value == 0:
                                        reporter.event(u_report.EVENT_TYPE_TEST,
                                                       u_report.EVENT_COMPLETE)
                                    else:
                                        reporter.event(u_report.EVENT_TYPE_TEST,
                                                       u_report.EVENT_FAILED)
                                else:
                                    reporter.event(u_report.EVENT_TYPE_DOWNLOAD,
                                                   u_report.EVENT_FAILED,
                                                   "check debug log for details")
                            else:
                                reporter.event(u_report.EVENT_TYPE_INFRASTRUCTURE,
                                               u_report.EVENT_FAILED,
                                               "unable to lock a connection")
                    else:
                        return_value = 1
                        reporter.event(u_report.EVENT_TYPE_BUILD,
                                       u_report.EVENT_FAILED,
                                       "check debug log for details")
                else:
                    return_value = 1
                    reporter.event(u_report.EVENT_TYPE_INFRASTRUCTURE,
                                   u_report.EVENT_FAILED,
                                   "unable to find overlay file")
            else:
                reporter.event(u_report.EVENT_TYPE_INFRASTRUCTURE,
                               u_report.EVENT_FAILED,
                               "environment setup failed")
        else:
            reporter.event(u_report.EVENT_TYPE_INFRASTRUCTURE,
                           u_report.EVENT_FAILED,
                           "there is a problem with the tools installation for Zephyr")

    return return_value
