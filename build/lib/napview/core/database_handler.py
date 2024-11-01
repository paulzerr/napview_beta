from peewee import *
import zlib
import struct
import numpy as np
import time
import os

# try:
#     from helpers import configure_logger
# except:
from .helpers import configure_logger

# setup the database via peewee
class EEGData(Model):
    index = IntegerField(primary_key=True)
    time = DateTimeField()
    data = BlobField()
    class Meta:
        table_name = 'eeg_data'

class EEGInfo(Model):
    recording_id = PrimaryKeyField()
    sample_rate  = IntegerField()
    start_time   = DateTimeField()
    n_channels   = IntegerField()
    channel_names   = CharField()
    class Meta:
        table_name = 'eeg_info'

class DatabaseHandler:
    def __init__(self, base_path):
        self.logger = configure_logger(base_path)
        self.logger.info('Database Handler: started...')

    def database_exists(self, db_file_path):
        return os.path.exists(db_file_path)  

    def get_total_n_samples(self):
        try:
            total_samples = EEGData.select().count()
            return total_samples
        except Exception as e:
            self.logger.error(f"Error in get_total_n_samples: {e}", exc_info=True)
            return None

    def get_most_recent_timestamp(self):
        try:
            timestamp = EEGData.select(fn.MAX(EEGData.time)).scalar()
            return timestamp
        except Exception as e:
            self.logger.error(f"Error in get_most_recent_timestamp: {e}", exc_info=True)
            return None

    def get_sample_timestamp(self, sample_index):
        try:
            timestamp = EEGData.select(EEGData.time).where(EEGData.index == sample_index).scalar()
            return timestamp
        except Exception as e:
            self.logger.error(f"Error in get_sample_timestamp: {e}", exc_info=True)
            return None

    def create_unique_db_filename(self, filepath):
        base, ext = os.path.splitext(filepath)
        for i in range(1, 100):
            new_filepath = f"{base}_{i}{ext}"
            if not os.path.exists(new_filepath):
                return new_filepath
        raise ValueError("Cannot create a unique filename.")

    def setup_database(self, db_file_path, create_tables):
        try:
            self.db = SqliteDatabase(db_file_path)
            EEGData._meta.database = self.db
            EEGInfo._meta.database = self.db
            self.db.connect()
            self.logger.info(f'Database Handler: db connected at {db_file_path}')
            if create_tables:
                self.db.create_tables([EEGData, EEGInfo], safe=True)
                self.logger.info('Database Handler: new db tables created...')
            return self.db
        except Exception as e:
            self.logger.error(f"Error in setup_database: {e}", exc_info=True)
            return None

    def create_info_entry(self, recording_id, sample_rate, n_channels, start_time, channel_names):
        try:
            EEGInfo.create(
                recording_id=recording_id,
                sample_rate=sample_rate,
                n_channels=n_channels,
                start_time=start_time,
                channel_names=channel_names
            )
            self.logger.info("Database Handler: EEG amp info created:")
            self.logger.info(f"  Recording ID: {recording_id}")
            self.logger.info(f"  Sample Rate: {sample_rate}")
            self.logger.info(f"  Number of Channels: {n_channels}")
            self.logger.info(f"  Start Time: {start_time}")
            self.logger.info(f"  Channel Names: {channel_names}")
        except Exception as e:
            self.logger.error(f"Error in create_info_entry: {e}", exc_info=True)

    def create_data_entry(self, sample, timestamp, sample_index):
        try:
            sample_compressed = zlib.compress(struct.pack(f'{len(sample)}f', *sample))
            EEGData.create(index=sample_index, time=timestamp, data=sample_compressed)
        except Exception as e:
            self.logger.error(f"Error in create_data_entry: {e}", exc_info=True)

    def retrieve_info(self, retries=100):
        for retry_count in range(retries):
            try:
                eeginfo = EEGInfo.get()
                return eeginfo
            except:
                self.logger.error(f"Database Handler: Database not found. Attempt {retry_count + 1}/{retries}. Waiting 1 second before retrying...")
                time.sleep(1)
        self.logger.error(f"Database Handler: Failed to retrieve EEGInfo after {retries} attempts. Aborting.", exc_info=True)
        return None

    def retrieve_data(self, start, end):
        try:
            selected_data = EEGData.select().where(
                (EEGData.index >= start) & (EEGData.index <= end)
            ).order_by(EEGData.index)
            self.eeg_info = self.retrieve_info()
            eeg_data = np.array([
                struct.unpack(f'{self.eeg_info.n_channels}f', zlib.decompress(data.data))
                for data in selected_data
            ])
            return eeg_data.T
        except Exception as e:
            self.logger.error(f"Error in retrieve_data: {e}", exc_info=True)
            return None

    def find_next_epoch_indices(self, number_analyzed_epochs, epoch_length_seconds):
        try:
            eeg_info = self.retrieve_info()
            samples_per_epoch = eeg_info.sample_rate * epoch_length_seconds
            start_sample_index = number_analyzed_epochs * samples_per_epoch
            end_sample_index = start_sample_index + samples_per_epoch - 1
            total_n_samples = self.get_total_n_samples()
            if total_n_samples is not None and total_n_samples >= end_sample_index:
                start_time = self.get_sample_timestamp(start_sample_index)
                return start_sample_index, end_sample_index, start_time
            else:
                return None, None, None
        except Exception as e:
            self.logger.error(f"Error in find_next_epoch_indices: {e}", exc_info=True)
            return None, None, None
