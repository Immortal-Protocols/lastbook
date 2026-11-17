# Saving the library on an external drive

The larger libraries are big: All needs close to 800 GB free while it installs. Many people put the library on an external
drive. This page explains what to do when setup will not save there, and covers the most common cause on a Mac in full:
**the drive is also a Time Machine backup disk.**

If setup shows one of these messages, this page is for you:

- `Lastbook cannot save in that folder. Choose another.`
- `Lastbook cannot make a folder there (…).`
- `“…” is not a Lastbook library. Choose the folder called LastbookData.`

## Contents

- [Quick answer](#quick-answer)
- [Step 1. Find out why the drive refuses](#step-1-find-out-why-the-drive-refuses)
- [Step 2. Time Machine disk: add a second volume](#step-2-time-machine-disk-add-a-second-volume)
- [Step 3. Point setup at the new volume](#step-3-point-setup-at-the-new-volume)
- [Other causes on a Mac](#other-causes-on-a-mac)
- [Windows and Linux](#windows-and-linux)
- [What each setup message means](#what-each-setup-message-means)
- [How much room to allow](#how-much-room-to-allow)

## Quick answer

On a Mac, a drive that Time Machine backs up to cannot hold anything else. macOS keeps that volume for backups only, so
no app can save files on it, however much free space it shows.

You do not need to erase the drive or stop your backups. Add a second volume to the same drive in Disk Utility
([Step 2](#step-2-time-machine-disk-add-a-second-volume)), then press **Change…** in setup and choose the new volume
([Step 3](#step-3-point-setup-at-the-new-volume)). It takes about two minutes.

## Step 1. Find out why the drive refuses

Free space is not the problem when you see the messages above. Setup shows a different message, with the numbers, when a
disk is too full. These messages mean the Mac will not let Lastbook write to the place you chose.

### Check in Finder

1. Select the drive in Finder's sidebar, or on the desktop.
2. Press **Command-I** (File > Get Info).
3. Read the **Format** line under General, and look at the drive's icon.

| What you see | What it means | What to do |
|---|---|---|
| Icon with a clock and a circular arrow, and Format `APFS (Case-sensitive)` or `APFS (Case-sensitive, Encrypted)` | A Time Machine backup volume. Backups only. | [Step 2](#step-2-time-machine-disk-add-a-second-volume) |
| Format `Windows NT File System (NTFS)` | A Windows format. A Mac can read it and cannot write to it. | [NTFS](#the-drive-is-formatted-for-windows-ntfs) |
| Format `MS-DOS (FAT32)` | Works for small files only. No file can be larger than 4 GB, and the library has larger ones. | [FAT32](#the-drive-is-formatted-fat32) |
| Format `APFS`, `Mac OS Extended (Journaled)` or `ExFAT`, with an ordinary drive icon | The format is fine. Something else is in the way. | [Other causes on a Mac](#other-causes-on-a-mac) |

You can also open **System Settings > General > Time Machine**. If the drive is listed there, it is a backup disk.

### Check in Terminal (optional)

Open Terminal (in Applications > Utilities). Replace `NAME` with the drive's name. Keep the quotation marks if the name has
a space in it.

This lists the disks Time Machine backs up to. If your drive's name is in the list, it is a backup disk:

```bash
tmutil destinationinfo
```

This tries to make an empty file on the drive:

```bash
touch "/Volumes/NAME/lastbook-test.txt"
```

| What Terminal answers | What it means |
|---|---|
| Nothing at all | The drive accepts files. The app has not been given access: see [Lastbook has not been given access](#lastbook-has-not-been-given-access). Delete the test file afterwards with `rm "/Volumes/NAME/lastbook-test.txt"`. |
| `Read-only file system` | The volume refuses all changes: a Time Machine volume, an NTFS drive, or a drive that needs repair. |
| `Operation not permitted` | macOS is protecting the volume (Time Machine does this), or Terminal itself has no access to removable drives. |
| `Permission denied` | The folder belongs to another user account: see [The folder belongs to someone else](#the-folder-belongs-to-someone-else). |

## Step 2. Time Machine disk: add a second volume

A drive formatted APFS can hold several volumes. They show up in Finder as separate drives, and they share the same free
space. So the drive can hold your backups on one volume and the library on another.

**This does not erase anything.** Your backups stay where they are and Time Machine keeps working.

1. Open **Disk Utility** (in Applications > Utilities).
2. In the menu bar, choose **View > Show All Devices**.
3. In the sidebar, select your backup volume (the one with the drive's name).
4. Press the **+** button above the word Volume in the toolbar, or choose **Edit > Add APFS Volume…**
5. **Name:** type a name that is different from the backup volume's, for example `Lastbook`.
6. **Format:** choose **APFS**, the first in the list.
   - Do not keep `APFS (Case-sensitive)`, which Disk Utility may offer first because the backup volume uses it. Time
     Machine needs it; ordinary apps expect the plain format. The format cannot be changed later without erasing the
     volume.
   - Choose `APFS (Encrypted)` only if you want to type a password each time the drive is plugged in. The library is
     public reference material, so most people do not need this.
7. Press **Size Options…**
   - **Reserve Size:** type the **Space needed** figure from Lastbook's setup screen, rounded up. For the All library
     with local AI, `800` GB. This keeps that much room for the library, so Time Machine cannot fill it as your backups
     grow.
   - **Quota Size:** leave empty. A quota is an upper limit, and a limit could stop a later library update.
8. Press **OK**, then **Add**.

The new volume appears in Finder's sidebar under Locations within a few seconds.

**Add is greyed out, or there is no Add APFS Volume in the menu?** The drive is not formatted APFS. An older Time Machine
disk formatted `Mac OS Extended (Journaled)` already accepts other files next to the backups, so look under
[Other causes on a Mac](#other-causes-on-a-mac) instead.

### The same thing in Terminal (optional)

Find the drive's container. Look for the line that says `APFS Container Scheme` above your backup volume and note its
identifier, such as `disk5`:

```bash
diskutil list external
```

Add the volume, replacing `disk5` with your identifier and `800g` with the room you want to reserve:

```bash
diskutil apfs addVolume disk5 APFS Lastbook -reserve 800g
```

## Step 3. Point setup at the new volume

1. In Lastbook's setup screen, press **Change…**, the button on the right of the **Saves to** line.
2. In the window that opens, select the new volume in the sidebar under Locations, and press the button to choose it.
   If the new volume is not in the sidebar, press **Command-Shift-G**, type `/Volumes/` and press Return.
3. **Saves to** now shows the new volume, for example `/Volumes/Lastbook/LastbookData`. Setup makes the `LastbookData`
   folder itself; you do not need to make it.
4. Press **Download and install**.

**Use Change…, not "Choose an existing library folder".** That link is for a library that is already downloaded, for
example one copied from another computer. If you use it on an empty volume, setup answers
`“…” is not a Lastbook library. Choose the folder called LastbookData.` Nothing is wrong with the drive. Go back and
press **Change…**

Keep the drive plugged in while Lastbook is open, and eject it in Finder before unplugging it.

## Other causes on a Mac

### Lastbook has not been given access

The first time an app saves to an external drive, macOS asks whether to allow it. If the answer was Don't Allow, the app
is refused from then on.

1. Open **System Settings > Privacy & Security > Files and Folders**.
2. Find **Lastbook** and turn on **Removable Volumes**.
3. Quit Lastbook, open it again, and press **Change…** to choose the folder again.

### The drive is formatted for Windows (NTFS)

A Mac reads NTFS drives and cannot write to them. The drive must be reformatted, and **reformatting erases everything on
it**, so copy anything you want to keep to another disk first.

1. Open **Disk Utility** and choose **View > Show All Devices**.
2. Select the drive itself, the top line for it in the sidebar, and press **Erase**.
3. **Scheme:** `GUID Partition Map`. **Format:** `APFS` if only Macs will use the drive, or `ExFAT` if Windows computers
   will use it too.

### The drive is formatted FAT32

FAT32 cannot hold a file larger than 4 GB. The local AI model alone is about 17 GB. Reformat the drive as described under
NTFS above. This also erases it.

### The drive is locked or needs repair

A drive that was unplugged without being ejected can come back read-only.

1. Open **Disk Utility**, select the volume, and press **First Aid**.
2. When it finishes, eject the drive, unplug it, and plug it in again.

Some drives and SD card adapters also have a small lock switch on the case. Check that it is off.

### The folder belongs to someone else

If the drive or folder was made by another user account or another Mac, your account may only be allowed to read it.

1. Select the drive in Finder and press **Command-I**.
2. Open **Sharing & Permissions** at the bottom. Next to your name it should say **Read & Write**.
3. If it does not, press the lock, and either change it to **Read & Write** or tick **Ignore ownership on this volume**.

Or choose a new, empty folder of your own on the same drive with **Change…**

## Windows and Linux

Time Machine is Mac only, but an external drive can refuse on other systems too.

**Windows**

- If the drive is write-protected, Windows refuses every app. Check for a lock switch on the drive or card adapter.
- Drives formatted FAT32 cannot hold a file larger than 4 GB. Reformat as NTFS or exFAT (this erases the drive).
- If setup says the folder is **too deep for Windows**, choose a folder closer to the top of the drive, such as `E:\`.
  The message gives the longest path that fits.

**Linux**

- A drive mounted by root, or mounted read-only, refuses your account. Check with `touch /path/to/drive/lastbook-test.txt`.
- An NTFS drive that Windows did not shut down fully (Fast Startup or hibernation) is mounted read-only. Start Windows,
  shut it down fully, and plug the drive in again.
- For a folder owned by root, make one of your own: `sudo mkdir /path/to/drive/Lastbook`, then
  `sudo chown "$USER" /path/to/drive/Lastbook`, and choose that folder in setup.

## What each setup message means

| Message | Meaning | What to do |
|---|---|---|
| `Lastbook cannot save in that folder. Choose another.` | The folder exists and the system will not let Lastbook write in it. | [Step 1](#step-1-find-out-why-the-drive-refuses) |
| `Lastbook cannot make a folder there (…).` | The system refused when setup tried to make the folder. The same causes apply. | [Step 1](#step-1-find-out-why-the-drive-refuses) |
| `“…” is not a Lastbook library. Choose the folder called LastbookData.` | "Choose an existing library folder" was used on a folder with no library in it. | Press **Change…** instead: [Step 3](#step-3-point-setup-at-the-new-volume) |
| `Lastbook cannot save in “LastbookData”. Move it somewhere you can save to, then choose it there.` | An existing library is on a volume that refuses changes. | Copy the `LastbookData` folder to a volume you can save to, then choose it there. |
| `There is already a folder called LastbookData there that is not a library. Choose another place.` | A folder with that name already holds other files. | Choose a different folder, or rename the old one. |
| `This needs … free on that disk, and it has …` | The disk is too full. | Free some space, choose a smaller library, or choose another disk. |

## How much room to allow

Setup shows three numbers. **Download** is what comes over the network. **Space needed** is larger, because the download
and the unpacked library are both on the disk until the install finishes. **Free on …** is what the disk has now.

Allow the **Space needed** figure. Once the install is done, the library takes about the "on disk" size shown next to
each choice, and the rest is free again.

On a shared Time Machine drive, the **Reserve Size** from [Step 2](#step-2-time-machine-disk-add-a-second-volume) is what
keeps that room for the library.

## Still stuck?

Open an issue at <https://github.com/Immortal-Protocols/lastbook/issues> and include:

- the exact message setup showed,
- the **Format** line from Get Info,
- what the `touch` command in [Step 1](#step-1-find-out-why-the-drive-refuses) answered.

Leave out the names of your computer, your account and your drives if they are personal.
