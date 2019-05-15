"""Script to install/uninstall HA into OS X."""
import os
import time


def install_osx():
    """Set up to run via launchd on OS X."""
    with os.popen('which opp') as inp:
        opp_path = inp.read().strip()

    with os.popen('whoami') as inp:
        user = inp.read().strip()

    template_path = os.path.join(os.path.dirname(__file__), 'launchd.plist')

    with open(template_path, 'r', encoding='utf-8') as inp:
        plist = inp.read()

    plist = plist.replace("$HASS_PATH$", opp_path)
    plist = plist.replace("$USER$", user)

    path = os.path.expanduser("~/Library/LaunchAgents/org.openpeerpower.plist")

    try:
        with open(path, 'w', encoding='utf-8') as outp:
            outp.write(plist)
    except IOError as err:
        print('Unable to write to ' + path, err)
        return

    os.popen('launchctl load -w -F ' + path)

    print("Open Peer Power has been installed. \
        Open it here: http://localhost:8123")


def uninstall_osx():
    """Unload from launchd on OS X."""
    path = os.path.expanduser("~/Library/LaunchAgents/org.openpeerpower.plist")
    os.popen('launchctl unload ' + path)

    print("Open Peer Power has been uninstalled.")


def run(args):
    """Handle OSX commandline script."""
    commands = 'install', 'uninstall', 'restart'
    if not args or args[0] not in commands:
        print('Invalid command. Available commands:', ', '.join(commands))
        return 1

    if args[0] == 'install':
        install_osx()
        return 0
    if args[0] == 'uninstall':
        uninstall_osx()
        return 0
    if args[0] == 'restart':
        uninstall_osx()
        # A small delay is needed on some systems to let the unload finish.
        time.sleep(0.5)
        install_osx()
        return 0