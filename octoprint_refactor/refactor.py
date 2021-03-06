import os.path
import concurrent.futures
import subprocess
import time


class Refactor:
    def __init__(self, settings):
        self.refactor_version_file = settings.get(["version_file"])
        self.klipper_dir = settings.get(["klipper_dir"])
        self.images_folder = settings.get(["images_folder"])
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.bytes_downloaded = 0
        self.bytes_to_download = 1
        self.download_cancelled = False
        self.is_download_finished = False
        self.install_progress = 0
        self.is_install_finished = False
        self.install_error = ""

    def get_refactor_version(self):
        with open(self.refactor_version_file, "r") as f:
            version = f.read().replace("\n", "")
            return version

    def get_klipper_version(self):
        import subprocess
        path = "git -C " + self.klipper_dir + " describe --always --tags --long --dirty"
        try:
            return subprocess.check_output(path.split()).strip()
        except subprocess.CalledProcessError:
            return "Unknown"

    def get_releases(self):
        import requests
        self.releases = requests.get(
            "https://api.github.com/repos/intelligent-agent/Refactor/releases")
        return self.releases.json()

    def get_local_releases(self):
        import glob
        images = [
            os.path.basename(f)
            for f in glob.glob(self.images_folder + "/*.img.xz")
        ]
        return images

    def download_version(self, refactor_version):
        url = refactor_version["assets"][0]['browser_download_url']
        self.bytes_downloaded = 0
        self.download_cancelled = False
        self.is_download_finished = False
        self.bytes_to_download = refactor_version["assets"][0]['size']
        filename = "Refactor-recore-" + refactor_version["name"] + ".img.xz"
        self.executor.submit(self.download_refactor, url, filename)

    def download_refactor(self, url, filename):
        import requests
        # Answer by Dennis Patterson
        # https://stackoverflow.com/questions/53101597/how-to-download-binary-file-using-requests
        #
        local_filename = self.images_folder + "/" + filename
        r = requests.get(url, stream=True)
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    self.bytes_downloaded += len(chunk)
                    if self.download_cancelled:
                        return
        self.is_download_finished = True

    def cancel_download(self):
        self.download_cancelled = True

    def get_download_progress(self):
        return {
            "progress": (self.bytes_downloaded / self.bytes_to_download),
            "cancelled": self.download_cancelled,
            "is_finished": self.is_download_finished
        }

    def install_version(self, filename):
        self.install_progress = 0
        self.is_install_finished = False
        self.bytes_transferred = 0
        ex = self.executor.submit(self.install_refactor, filename)

    def get_uncompressed_size(self, infile):
        line = subprocess.run(f"xz -l {infile} | grep MiB",
                              shell=True,
                              capture_output=True,
                              text=True).stdout
        try:
            size = float(line.split()[4].replace(",", "")) * 1024 * 1024
        except:
            self.install_error = "Unable to get uncompressed file size"
            size = 1
        return size

    def install_refactor(self, filename):
        infile = self.images_folder + "/" + filename
        if not os.path.isfile(infile):
            self.install_error = "Chosen file is not present"
            return
        cmd = ["sudo", "/usr/local/bin/flash-recore", infile]
        self.bytes_total = self.get_uncompressed_size(infile)
        self.bytes_transferred = 0
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        while True:
            time.sleep(0.3)
            if self.process.poll() == 0:
                self.is_install_finished = True
                break
            with open("/tmp/recore-flash-progress") as f:
                lines = f.readlines()
                if len(lines):
                    try:
                        self.bytes_transferred = int(lines[-1].strip())
                    except:
                        pass
            self.install_progress = self.bytes_transferred / self.bytes_total

    def get_install_progress(self):
        return {
            "progress": self.install_progress,
            "is_finished": self.is_install_finished,
            "error": self.install_error
        }

    def run_system_command(command):
        return subprocess.run(command.split(),
                              capture_output=True,
                              text=True).stdout.strip()

    def get_rootfs():
        return Refactor.run_system_command("/usr/local/bin/get-rootfs")

    def get_boot_media(self):
        return Refactor.run_system_command("sudo /usr/local/bin/get-boot-media")

    def change_boot_media(self):
        if self.get_boot_media() == "emmc":
            os.system("sudo /usr/local/bin/set-boot-media usb")
        else:
            os.system("sudo /usr/local/bin/set-boot-media emmc")

    def is_usb_present():
        return Refactor.run_system_command("/usr/local/bin/is-media-present usb") == "yes"

    def is_emmc_present():
        return Refactor.run_system_command("/usr/local/bin/is-media-present emmc") == "yes"
