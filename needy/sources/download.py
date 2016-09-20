from __future__ import print_function

import io
import os
import binascii
import hashlib
import socket
import shutil
import sys
import tarfile
import tempfile
import time
import zipfile
import logging

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

from ..source import Source


class Download(Source):
    def __init__(self, url, checksum, destination, cache_directory):
        Source.__init__(self)
        self.url = url
        self.checksum = checksum
        self.destination = destination
        self.cache_directory = cache_directory
        self.local_download_path = os.path.join(cache_directory, checksum)

    @classmethod
    def identifier(cls):
        return 'download'

    def clean(self):
        if not self.checksum:
            raise ValueError('checksums are required for downloads')

        self.__fetch()

        logging.info('Unpacking to %s' % self.destination)
        self.__clean_destination_dir()
        self.__unpack()
        self.__trim_lone_dirs()

    def __fetch(self):
        if not os.path.exists(self.cache_directory):
            os.makedirs(self.cache_directory)

        if not os.path.isfile(self.local_download_path):
            self.get(self.url, self.checksum, self.local_download_path)

    @classmethod
    def get(cls, url, checksum, destination):
        logging.info('Downloading from %s' % url)
        download = None
        attempts = 0
        download_successful = False
        while not download_successful and attempts < 5:
            try:
                download = urllib2.urlopen(url, timeout=5)
            except urllib2.URLError as e:
                logging.warning(e)
            except socket.timeout as e:
                logging.warning(e)
            attempts = attempts + 1
            download_successful = download and download.code == 200 and 'content-length' in download.info()
            if not download_successful:
                logging.warning('Download failed. Retrying...')
            time.sleep(attempts)
        if not download_successful:
            raise IOError('unable to download library')
        size = int(download.info()['content-length'])
        progress = 0
        if sys.stdout.isatty():
            print('{:.1%}'.format(float(progress) / size), end='')
            sys.stdout.flush()

        local_file = tempfile.NamedTemporaryFile('wb', delete=False)
        try:
            chunk_size = 1024
            while True:
                chunk = download.read(chunk_size)
                progress = progress + chunk_size
                if sys.stdout.isatty():
                    print('\r{:.1%}'.format(float(progress) / size), end='')
                    sys.stdout.flush()
                if not chunk:
                    break
                local_file.write(chunk)

            local_file.close()
            if sys.stdout.isatty():
                print('\r       \r', end='')
                sys.stdout.flush()

            logging.debug('Verifying checksum...')
            if not cls.verify_checksum(local_file.name, checksum):
                raise ValueError('incorrect checksum')
            logging.debug('Checksum verified.')

            shutil.move(local_file.name, destination)
        except:
            os.unlink(local_file.name)
            raise

        del download

    @classmethod
    def verify_checksum(cls, path, expected):
        expected = binascii.unhexlify(expected)

        with open(path, 'rb') as file:
            file_contents = file.read()
            hash = None
            if len(expected) == hashlib.md5().digest_size:
                hash = hashlib.md5()
            elif len(expected) == hashlib.sha1().digest_size:
                hash = hashlib.sha1()
            else:
                raise ValueError('unknown checksum type')
            hash.update(file_contents)
            return expected == hash.digest()

    def __clean_destination_dir(self):
        if os.path.exists(self.destination):
            shutil.rmtree(self.destination)
        os.makedirs(self.destination)

    def __unpack(self):
        if tarfile.is_tarfile(self.local_download_path):
            self.__tarfile_unpack()
            return
        if zipfile.is_zipfile(self.local_download_path):
            self.__zipfile_unpack()
            return

    def __tarfile_unpack(self):
        with open(self.local_download_path, 'rb') as file:
            tar = tarfile.open(fileobj=file, mode='r|*')
            tar.extractall(self.destination if isinstance(self.destination, str) else self.destination.encode(sys.getfilesystemencoding()))
            del tar

    def __zipfile_unpack(self):
        with zipfile.ZipFile(self.local_download_path, 'r') as file:
            file.extractall(self.destination)

    def __trim_lone_dirs(self):
        temporary_directory = os.path.join(self.cache_directory, 'temp_')

        while True:
            destination_contents = os.listdir(self.destination)
            if len(destination_contents) != 1:
                break
            lone_directory = os.path.join(self.destination, destination_contents[0])
            if not os.path.isdir(lone_directory):
                break
            shutil.move(lone_directory, temporary_directory)
            shutil.rmtree(self.destination)
            shutil.move(temporary_directory, self.destination)
