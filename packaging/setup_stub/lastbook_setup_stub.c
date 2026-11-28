// Lastbook-<version>-Setup.exe: a small front for the real installer (lastbook_setup.py, a PyInstaller one-file program).
//
// Why: a one-file PyInstaller program loads VCRUNTIME140.dll, VCRUNTIME140_1.dll and mscoree.dll by bare name, and Windows looks
// in the program's own folder first. For a downloaded installer that folder is Downloads, so a DLL planted there would run
// (security audit N-DLL). This front imports only kernel32 and user32 (known DLLs, never searched for), allows DLLs from System32 only,
// writes the real installer into a new private folder under this person's temporary folder, runs it from there with the same
// command line, waits, removes it, and exits with its exit code. The real installer's own folder is then that private folder.
//
// The real installer is appended to this file: [stub][installer bytes][8-byte size, little-endian]["LBSETUP1"].
// Authenticode may append alignment bytes and a certificate table after this footer.
// No C runtime: built with -nostdlib, so nothing else is loaded before the first line runs.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "i18n_messages.h"

#ifndef LOAD_LIBRARY_SEARCH_SYSTEM32
#define LOAD_LIBRARY_SEARCH_SYSTEM32 0x00000800
#endif

// With no C runtime, the compiler may still turn a zeroing loop into a call to memset: this is it.
void *memset(void *d, int c, unsigned long long n) {
    volatile unsigned char *p = (volatile unsigned char *)d;
    while (n--) *p++ = (unsigned char)c;
    return d;
}

static const char MAGIC[8] = {'L', 'B', 'S', 'E', 'T', 'U', 'P', '1'};

static unsigned installer_locale(void);
static void fail(unsigned message);
static void wcat(wchar_t *dst, int cap, const wchar_t *src);

static void fail(unsigned message) {
    unsigned locale = installer_locale();
    MessageBoxW(NULL, stub_message(locale, message), stub_message(locale, STUB_SETUP_TITLE), MB_OK | MB_ICONERROR);
    ExitProcess(1);
}

static int same8(const char *a, const char *b) {
    for (int i = 0; i < 8; i++) if (a[i] != b[i]) return 0;
    return 1;
}

static void wcat(wchar_t *dst, int cap, const wchar_t *src) {
    int n = 0;
    while (n < cap - 1 && dst[n]) n++;
    while (n < cap - 1 && *src) dst[n++] = *src++;
    dst[n] = 0;
}

static int bytes_equal(const char *value, unsigned length, const char *expected) {
    unsigned i = 0;
    while (expected[i] && i < length && value[i] == expected[i]) i++;
    return i == length && expected[i] == 0;
}

static unsigned locale_from_tag(const char *value, unsigned length) {
    if (bytes_equal(value, length, "en")) return STUB_LOCALE_EN;
    if (bytes_equal(value, length, "es-419")) return STUB_LOCALE_ES_419;
    if (bytes_equal(value, length, "de")) return STUB_LOCALE_DE;
    if (bytes_equal(value, length, "zh-Hans")) return STUB_LOCALE_ZH_HANS;
    return 0xffffffffu;
}

static unsigned saved_locale(const char *data, unsigned length) {
    static const char key[] = "\"language\"";
    for (unsigned i = 0; i + sizeof(key) - 1 <= length; i++) {
        unsigned j = 0;
        while (j < sizeof(key) - 1 && data[i + j] == key[j]) j++;
        if (j != sizeof(key) - 1) continue;
        unsigned at = i + j;
        while (at < length && (data[at] == ' ' || data[at] == '\t' || data[at] == '\r' || data[at] == '\n')) at++;
        if (at >= length || data[at++] != ':') continue;
        while (at < length && (data[at] == ' ' || data[at] == '\t' || data[at] == '\r' || data[at] == '\n')) at++;
        if (at >= length || data[at++] != '"') continue;
        unsigned start = at;
        while (at < length && data[at] != '"' && data[at] != '\\' && data[at] != '\r' && data[at] != '\n') at++;
        if (at < length && data[at] == '"') return locale_from_tag(data + start, at - start);
    }
    return 0xffffffffu;
}

static unsigned installer_locale(void) {
    static wchar_t path[32768];
    DWORD length = GetEnvironmentVariableW(L"APPDATA", path, 32768);
    if (length > 0 && length < 32768) {
        wcat(path, 32768, L"\\Lastbook\\ui-language.json");
        HANDLE preference = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                                        FILE_ATTRIBUTE_NORMAL, NULL);
        if (preference != INVALID_HANDLE_VALUE) {
            LARGE_INTEGER size;
            if (GetFileSizeEx(preference, &size) && size.QuadPart > 0 && size.QuadPart <= 4096) {
                static char data[4096];
                DWORD read = 0;
                if (ReadFile(preference, data, (DWORD)size.QuadPart, &read, NULL) && read == (DWORD)size.QuadPart) {
                    unsigned locale = saved_locale(data, read);
                    if (locale != 0xffffffffu) { CloseHandle(preference); return locale; }
                }
            }
            CloseHandle(preference);
        }
    }
    LANGID language = GetUserDefaultUILanguage();
    if ((language & 0x3ff) == 0x0a) return STUB_LOCALE_ES_419;
    if ((language & 0x3ff) == 0x07) return STUB_LOCALE_DE;
    if (language == 0x0804 || language == 0x1004) return STUB_LOCALE_ZH_HANS;
    return STUB_LOCALE_EN;
}

static void whex(wchar_t *dst, int cap, unsigned long v) {
    wchar_t b[9];
    for (int i = 7; i >= 0; i--) { b[i] = L"0123456789abcdef"[v & 15]; v >>= 4; }
    b[8] = 0;
    wcat(dst, cap, b);
}

// The command line after this program's own name, as Windows gave it (quoted name or not).
static const wchar_t *args_after_name(const wchar_t *cl) {
    if (*cl == L'"') { cl++; while (*cl && *cl != L'"') cl++; if (*cl) cl++; }
    else { while (*cl && *cl != L' ' && *cl != L'\t') cl++; }
    while (*cl == L' ' || *cl == L'\t') cl++;
    return cl;
}

void WinMainCRTStartup(void) {
    // Before anything else: DLLs for this process come from System32 only, never from the folder this file is in.
    SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32);
    SetDllDirectoryW(L"");     // and take the current folder out of the old search order too

    static wchar_t self[32768];
    if (!GetModuleFileNameW(NULL, self, 32768)) fail(STUB_SELF_MISSING);
    HANDLE f = CreateFileW(self, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) fail(STUB_SELF_UNREADABLE);
    LARGE_INTEGER total;
    if (!GetFileSizeEx(f, &total) || total.QuadPart < 16) fail(STUB_DAMAGED);
    BYTE *image = (BYTE *)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)image;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(image + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY certificate = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_SECURITY];
    LONGLONG payload_end = total.QuadPart;
    if (certificate.Size) {
        if (certificate.VirtualAddress < 16 ||
            (ULONGLONG)certificate.VirtualAddress + certificate.Size > (ULONGLONG)total.QuadPart)
            fail(STUB_DAMAGED);
        // Unlike other PE directories, the certificate table uses a file offset.
        payload_end = certificate.VirtualAddress;
    }
    char tail[16];
    DWORD got = 0;
    LARGE_INTEGER pos;
    int found = 0;
    // SignTool aligns the certificate table to eight bytes. The footer can precede up to seven padding bytes.
    for (int padding = 0; padding < 8 && payload_end >= 16 + padding; padding++) {
        pos.QuadPart = payload_end - 16 - padding;
        if (!SetFilePointerEx(f, pos, NULL, FILE_BEGIN) || !ReadFile(f, tail, 16, &got, NULL) || got != 16)
            fail(STUB_DAMAGED);
        if (same8(tail + 8, MAGIC)) { payload_end -= padding; found = 1; break; }
    }
    if (!found) fail(STUB_DAMAGED);
    unsigned long long size = 0;
    for (int i = 7; i >= 0; i--) size = (size << 8) | (unsigned char)tail[i];
    if (size == 0 || size > (unsigned long long)payload_end - 16) fail(STUB_DAMAGED);
    pos.QuadPart = payload_end - 16 - (LONGLONG)size;

    // A new folder of this person's own, under their temporary folder (only they and the system can write there).
    static wchar_t dir[MAX_PATH + 64], exe[MAX_PATH + 96];
    DWORD n = GetTempPathW(MAX_PATH, dir);
    if (!n || n > MAX_PATH) fail(STUB_TEMP_MISSING);
    int made = 0;
    for (int tries = 0; tries < 20 && !made; tries++) {
        dir[n] = 0;
        wcat(dir, MAX_PATH + 64, L"LastbookSetup-");
        whex(dir, MAX_PATH + 64, GetCurrentProcessId());
        whex(dir, MAX_PATH + 64, GetTickCount() + (DWORD)tries * 7919u);
        made = CreateDirectoryW(dir, NULL);     // fails if it exists: never reuse a folder someone else made
    }
    if (!made) fail(STUB_TEMP_CREATE);
    exe[0] = 0;
    wcat(exe, MAX_PATH + 96, dir);
    wcat(exe, MAX_PATH + 96, L"\\Lastbook Setup.exe");
    HANDLE o = CreateFileW(exe, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (o == INVALID_HANDLE_VALUE) { RemoveDirectoryW(dir); fail(STUB_TEMP_WRITE); }
    if (!SetFilePointerEx(f, pos, NULL, FILE_BEGIN)) fail(STUB_SELF_UNREADABLE);
    static char buf[1 << 20];
    unsigned long long left = size;
    while (left) {
        DWORD want = left > sizeof(buf) ? (DWORD)sizeof(buf) : (DWORD)left, r = 0, w = 0;
        if (!ReadFile(f, buf, want, &r, NULL) || r != want || !WriteFile(o, buf, r, &w, NULL) || w != r) {
            CloseHandle(o); DeleteFileW(exe); RemoveDirectoryW(dir); fail(STUB_UNPACK_FAILED);
        }
        left -= r;
    }
    CloseHandle(o);
    CloseHandle(f);

    // Run it with the same arguments (/S, /uninstall), from its own folder, and wait.
    static wchar_t cmd[32768];
    cmd[0] = 0;
    wcat(cmd, 32768, L"\"");
    wcat(cmd, 32768, exe);
    wcat(cmd, 32768, L"\" ");
    wcat(cmd, 32768, args_after_name(GetCommandLineW()));
    STARTUPINFOW si; PROCESS_INFORMATION pi;
    for (unsigned i = 0; i < sizeof(si); i++) ((char *)&si)[i] = 0;
    si.cb = sizeof(si);
    DWORD code = 1;
    if (CreateProcessW(exe, cmd, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        GetExitCodeProcess(pi.hProcess, &code);
        CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    } else {
        DeleteFileW(exe); RemoveDirectoryW(dir);
        fail(STUB_START_FAILED);
    }
    for (int i = 0; i < 50 && !DeleteFileW(exe); i++) Sleep(100);     // the installer's own clean-up can hold it a moment
    RemoveDirectoryW(dir);
    ExitProcess(code);
}
