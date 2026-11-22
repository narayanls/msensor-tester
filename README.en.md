# MSensor Tester

[Português](README.md) · **English**

Mouse **sensor tracking** and **polling rate** tester for Linux, written in Python with GTK 4 and libadwaita.

The **Sensor** tab follows the Windows [MouseTester](https://github.com/microe1/MouseTester): it measures the real CPI, records the movement and shows count and trajectory plots. The **Polling rate** tab measures how many reports per second the mouse actually sends, live, with statistics a browser-based test cannot provide.

The interface is in English, and in Portuguese (pt-BR) on systems set to Portuguese.

## Installation

### Prebuilt package (Arch Linux and derivatives)

Works on Arch Linux and derivatives such as CachyOS, EndeavourOS and Manjaro.

1. Download `msensor-tester-<version>-1-any.pkg.tar.zst` from the [Releases](https://github.com/narayanls/msensor-tester/releases/latest) page.
2. Install it with pacman, from the folder where you saved it:

   ```sh
   sudo pacman -U msensor-tester-1.0.0-1-any.pkg.tar.zst
   ```

pacman installs the dependencies (`python`, `python-gobject`, `gtk4`, `libadwaita`, `python-numpy` and `python-matplotlib`) and applies the udev rule that grants access to the mice. Then open **MSensor Tester** from the application menu or run `msensor-tester` in a terminal.

To update, download the new version's package and run `pacman -U` again. To remove:

```sh
sudo pacman -R msensor-tester
```

### Build from source

```sh
git clone https://github.com/narayanls/msensor-tester.git
cd msensor-tester/pkgbuild
makepkg -si
```

`makepkg` produces the same `.pkg.tar.zst` file published in Releases, inside the `pkgbuild` folder.

### Run without installing

```sh
python3 usr/share/msensor-tester/main.py
```

In this case the udev rule is not installed; see [Access to the mice](#access-to-the-mice).

## How it works

The app reads the mouse directly from **evdev** (`/dev/input/eventN`), the Linux equivalent of the Raw Input API used by MouseTester:

- **Raw sensor counts**, without pointer acceleration.
- **Each report is timestamped by the kernel**, in microseconds. Python or UI delays do not affect the measurement.
- **Works the same on Wayland and X11**, because reading the mouse depends neither on the compositor nor on window focus.

The **cursor keeps moving normally during the tests**, as in the original MouseTester. This does not affect the measurement: the app reads the sensor straight from the kernel, even with the cursor stopped at the edge of the screen.

During **Measure CPI** and **Collect**, a test area covers the tab. Start the click with the cursor over it: the system (Wayland or X11) delivers the whole drag to the app until you release the button, even if the cursor leaves the window, so nothing gets dragged or selected on the desktop. **Esc cancels at any time.**

There is an optional cursor lock in **Menu → Preferences** (off by default). It requests exclusive access to the mouse and fails if another program already has it, such as input-remapper, keyd or kanata. In that case the app shows the reason and the test continues without the lock.

### Sensor tab

- **Measure CPI**: hold the left button, move the mouse 10 cm in a straight line (use a ruler) and release. The distance can be changed in Preferences.
- **Collect (F1)**: records while the left button is held.
- **Plots (F3)**: X, Y and XY counts vs. time, and X vs. Y trajectory. You can choose the event range, toggle lines, stems and the 8 ms smoothed average, zoom and export a PNG.
- **Save / Open CSV**: in the **same format as MouseTester**. Logs recorded on Windows open here and vice versa, so you can compare the same mouse on both systems.

### Polling rate tab

Click **Start test (F1)** and move the mouse quickly in all directions. The timer starts with the first movement and lasts the chosen duration (5 to 60 s). During the test you see the current rate, a graph of the rate over time and a histogram of the intervals. At the end, the app shows:

- **Detected rate**: 125, 250, 500, 1000, 2000, 4000 or 8000 Hz.
- **Average, peak and lowest rate**, over 100 ms windows.
- **Intervals between reports**: mean, median, shortest, longest, 1st and 99th percentiles.
- **Jitter** (standard deviation) and the share of intervals within ±25% of the nominal value.
- Pauses in movement and kernel buffer overflows.

The mouse only sends reports while it moves, so **pauses are excluded from the calculations**. The rate is computed by counting reports over time, which is not fooled when the USB controller delivers two reports almost together.

## Access to the mice

Reading `/dev/input` requires permission. Instead of adding the user to the `input` group, which would also grant access to the keyboard, the package installs the udev rule `/usr/lib/udev/rules.d/70-msensor-tester.rules`. It grants read access **to mice only**, and only to the user logged in at the computer, through systemd-logind's `uaccess` tag.

The package applies the rule on installation, via `pacman -U` or `makepkg -si`. If the app says permission is missing, reconnect the mouse or run:

```sh
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=input --action=change
```

To run straight from the repository without installing the package, copy the rule first:

```sh
sudo install -Dm644 usr/lib/udev/rules.d/70-msensor-tester.rules /etc/udev/rules.d/70-msensor-tester.rules
```

## When nothing is captured (diagnostics)

If the test opens but no movement shows up, run the diagnostic with the app closed:

```sh
msensor-tester --diagnose
# without installing: python3 usr/share/msensor-tester/main.py --diagnose
```

During the 5-second listening test, move the mouse and click. The report shows:
- every input device and its permissions;
- whether the udev rule was applied (`uaccess` tag);
- whether another program has exclusive access to the mouse;
- which known input-grabbing programs are running;
- how many events each mouse sent during the listening test.

The same report is available in **Menu → Diagnostics**, with a copy button.

To follow every step of the app, run it with debug logging:

```sh
msensor-tester --debug
```

The log goes to the terminal and to `~/.cache/msensor-tester/debug.log`. Every second of a test it shows how many raw events arrived (the debug log is in Portuguese: look for "eventos brutos"); 0 raw events while you move the mouse means the kernel is delivering nothing to this app.

**Most common cause:** a program that grabs the mouse exclusively (button and macro remappers such as input-remapper, keyd, kanata, logiops, interception-tools, xremap, or your own python-evdev script). While it runs, the kernel delivers the events only to that program, which forwards them through a virtual device. The app detects this before each test, shows which process is holding the mouse and offers to use the virtual device. In the list, these mice are marked "in exclusive use" and "virtual". To fix it, close the program during the test or select the virtual device in the list (the polling rate measured will be the virtual device's, not the mouse's).

## Tips and limitations

- **Some USB controllers batch interrupts**: intervals may alternate (for example 0.9 and 1.1 ms) instead of staying constant. This is real hardware behavior and also happens on Windows; the histogram makes it visible.
- **Old mice at 125 Hz**: the kernel accepts the `usbhid.mousepoll` parameter to force another rate on mice that do not request one. Modern gaming mice already request the right rate.
- **The F1, F3 and Esc keys** only work while the app window has focus.
- **In the polling rate test**, prefer moving the mouse in circles in the middle of the screen: hitting a corner may open the GNOME overview (hot corner). The measurement continues, but the window goes to the background.

## Credits

Inspired by [MouseTester](https://github.com/microe1/MouseTester) by microe1 (MIT). MSensor Tester is an independent reimplementation for Linux; no code from the original was copied.

## License

[GPL-3.0-or-later](LICENSE)
