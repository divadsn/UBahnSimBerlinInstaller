import enum

from typing import Optional
from usb_installer import DLL_PATH

import clr

clr.AddReference("System")
clr.AddReference("System.Windows.Forms")

import System
import System.Windows.Forms as WinForms

clr.AddReference(str(DLL_PATH / "Microsoft.WindowsAPICodePack.dll"))
clr.AddReference(str(DLL_PATH / "Microsoft.WindowsAPICodePack.Shell.dll"))

from Microsoft.WindowsAPICodePack.Dialogs import CommonOpenFileDialog, CommonFileDialogResult
from Microsoft.WindowsAPICodePack.Taskbar import TaskbarManager, TaskbarProgressBarState


class MessageBoxButtons(enum.IntEnum):
    OK = 0
    OK_CANCEL = 1
    ABORT_RETRY_IGNORE = 2
    YES_NO_CANCEL = 3
    YES_NO = 4
    RETRY_CANCEL = 5


class MessageBoxIcon(enum.IntEnum):
    NONE = 0
    ERROR = 16
    QUESTION = 32
    WARNING = 48
    INFORMATION = 64


class MessageBoxDefaultButton(enum.IntEnum):
    BUTTON1 = 0
    BUTTON2 = 256
    BUTTON3 = 512


class DialogResult(enum.IntEnum):
    NONE = 0
    OK = 1
    CANCEL = 2
    ABORT = 3
    RETRY = 4
    IGNORE = 5
    YES = 6
    NO = 7


class TaskbarProgressState(enum.IntEnum):
    NO_PROGRESS = 0
    INDETERMINATE = 0x1
    NORMAL = 0x2
    ERROR = 0x4
    PAUSED = 0x8


def show_message_box(
    message: str,
    title: str = "Message",
    buttons: MessageBoxButtons = MessageBoxButtons.OK,
    icon: MessageBoxIcon = MessageBoxIcon.INFORMATION,
    default_button: MessageBoxDefaultButton = MessageBoxDefaultButton.BUTTON1,
    window: Optional[WinForms.IWin32Window] = None,
) -> DialogResult:
    args = [message, title, System.Enum.ToObject(WinForms.MessageBoxButtons, buttons), System.Enum.ToObject(WinForms.MessageBoxIcon, icon), System.Enum.ToObject(WinForms.MessageBoxDefaultButton, default_button)]

    if window:
        args.insert(0, window)

    return DialogResult(int(WinForms.MessageBox.Show(*args)))


def show_folder_picker_dialog(
    title: Optional[str] = None,
    initial_directory: Optional[str] = None,
    window: Optional[WinForms.IWin32Window] = None,
) -> Optional[str]:
    dialog = CommonOpenFileDialog()
    dialog.IsFolderPicker = True

    if title:
        dialog.Title = title

    if initial_directory:
        dialog.InitialDirectory = initial_directory

    if dialog.ShowDialog(window.Handle) == CommonFileDialogResult.Ok and dialog.FileName:
        return dialog.FileName

    return None


def set_taskbar_progress(
    state: TaskbarProgressState,
    value: Optional[int] = None,
    max_value: Optional[int] = None,
):
    TaskbarManager.Instance.SetProgressState(System.Enum.ToObject(TaskbarProgressBarState, state))

    if value is not None and max_value is not None:
        TaskbarManager.Instance.SetProgressValue(value, max_value)
