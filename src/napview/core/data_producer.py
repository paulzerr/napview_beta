import time
import socket
import numpy as np
import mne
from pylsl import StreamInfo, StreamOutlet
from struct import unpack
from pathlib import Path

try:
    from helpers import configure_logger, ConfigManager
except:
    from .helpers import configure_logger, ConfigManager


class DataProducer:
    def __init__(self, base_path, mode):
        self.logger = configure_logger(base_path)
        self.logger.info('Producer: started')
        self.mode = mode
        self.base_path = base_path
        self.config_manager = ConfigManager(base_path)
        self.config = self.config_manager.load_config(instance=self)

    def load_edf_data(self):
        try:
            self.sim_input_file_path = Path(self.base_path) / "eeg.edf"
            self.logger.info(f"Producer: Attempting to read edf file at {self.sim_input_file_path}.")
            raw = mne.io.read_raw_edf(self.sim_input_file_path, preload=True)
            self.logger.info(f"Producer: Successfully read the EEG file at {self.sim_input_file_path}.")
            self.sample_rate = int(raw.info['sfreq'])
            self.n_channels = len(raw.info['ch_names'])
            self.channel_names = raw.info['ch_names']
            data, _ = raw[:, :]
            self.data = data.T
            self.logger.info(f"Producer: Loaded EDF file details:")
            self.logger.info(f"     Sample rate: {self.sample_rate} Hz")
            self.logger.info(f"     Number of channels: {self.n_channels}")
            self.logger.info(f"     Channel names: {self.channel_names}")
            self.logger.info(f"     Data shape: {self.data.shape}")
            self.logger.info('Producer: EDF loaded')
        except Exception as e:
            self.logger.error(f"Producer: Failed to read the EEG file at {self.sim_input_file_path}: {e}", exc_info=True)


    def connect_brainvision_rda(self, max_retries=10,retry_delay = 1):
        self.config = self.config_manager.load_config(instance=self)
        self.amp_ip = self.config.get('amp_ip', '127.0.0.1')
        self.port = self.config.get('amp_port', 51244)
        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(f"Producer: Attempting to connect to {self.amp_ip}:{self.port}")
                self.con = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.con.connect((self.amp_ip, self.port))
                self.logger.info(f"Producer: Connected to {self.amp_ip}:{self.port}")
                return
            except Exception as e:
                self.logger.error(f"Producer: Connection attempt {attempt} failed: {e}", exc_info=True)
                if attempt < max_retries:
                    self.logger.info(f"Producer: Retrying in {retry_delay} second(s)...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"Producer: Max EEG amp connection retries reached. Unable to connect. {e}", exc_info=True)

    def get_amp_info(self, max_retries=10, retry_delay=1):
        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(f"Producer: Attempting to retrieve EEG info from amp.")
                raw_data_chunk, message_type = self.unpack_raw_message()
                if message_type == 1:
                    (n_channels, self.sample_rate, resolutions, self.channel_names) = self.unpack_header(raw_data_chunk)
                    self.logger.info(f" amp info: Number of channels: {n_channels}")
                    self.logger.info(f" amp info: Sampling interval: {self.sample_rate} Hz")
                    self.logger.info(f" amp info: Resolutions: {resolutions}")
                    self.logger.info(f" amp info: Channel Names: {self.channel_names}")
                    return n_channels, self.sample_rate, resolutions, self.channel_names
            except Exception as e:
                self.logger.error(f"Producer: Attempt {attempt} failed to get amp info: {e}", exc_info=True)
                if attempt < max_retries:
                    self.logger.info(f"Producer: Retrying in {retry_delay} second(s)...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"Producer: Max info retrieval retries reached. Unable to get EEG amp info. {e}", exc_info=True)

    def get_data_chunk(self, n_channels, lastBlock):
        try:
            raw_data_chunk, message_type = self.unpack_raw_message()
            if message_type == 4:
                (block, points, markerCount, data) = self.unpack_data_chunk(raw_data_chunk, n_channels)
                if lastBlock != -1 and block > lastBlock + 1:
                    self.logger.warning(f"Producer: Data overflow with {block - lastBlock} datablocks !!")
                lastBlock = block
                return data, lastBlock
            return None, lastBlock
        except Exception as e:
            self.logger.error(f"Producer: Error getting data chunk: {e}", exc_info=True)


    def receive_data_chunk(self, requestedSize):
        returnStream = bytearray()
        while len(returnStream) < requestedSize:
            try:
                databytes = self.con.recv(requestedSize - len(returnStream))
                if not databytes:
                    self.logger.error(f"Producer: Connection broken: {e}", exc_info=True)
                returnStream += databytes
            except Exception as e:
                self.logger.error(f"Producer: Error receiving data chunk: {e}", exc_info=True)

        return returnStream

    def split_string(self, raw):
        stringlist = []
        s = ""
        for i in raw:
            if i != 0:
                s += chr(i)
            else:
                stringlist.append(s)
                s = ""
        return stringlist

    def unpack_header(self, raw_data_chunk):
        try:
            (n_channels, self.sample_rate) = unpack('<Ld', raw_data_chunk[:12])
            resolutions = [unpack('<d', raw_data_chunk[12 + c * 8:12 + (c + 1) * 8])[0] for c in range(n_channels)]
            self.channel_names = self.split_string(raw_data_chunk[12 + 8 * n_channels:])
            return (n_channels, self.sample_rate, resolutions, self.channel_names)
        except Exception as e:
            self.logger.error(f"Producer: Error unpacking header: {e}", exc_info=True)


    def unpack_data_chunk(self, raw_data_chunk, n_channels):
        try:
            (block, points, markerCount) = unpack('<LLL', raw_data_chunk[:12])
            data = [unpack('<f', raw_data_chunk[12 + 4 * i:12 + 4 * (i + 1)])[0] for i in range(points * n_channels)]
            return (block, points, markerCount, data)
        except Exception as e:
            self.logger.error(f"Producer: Error unpacking data chunk: {e}", exc_info=True)


    def unpack_raw_message(self):
        try:
            rraw_message_header = self.receive_data_chunk(24)
            (id1, id2, id3, id4, message_size, message_type) = unpack('<llllLL', rraw_message_header)
            raw_data_chunk = self.receive_data_chunk(message_size - 24)
            return raw_data_chunk, message_type
        except Exception as e:
            self.logger.error(f"Producer: Error unpacking raw message: {e}", exc_info=True)


    def setup_openbci(self):
        try:
            from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
            openbci_params = BrainFlowInputParams()
            self.config = self.config_manager.load_config(instance=self)
            board_type = self.config.get('board_type', 'simulation')
            openbci_port = self.config.get('openbci_port', 'COM3')
            if board_type == 'Cyton':
                openbci_params.serial_port = self.config.get('serial_port', openbci_port)
                board_id = BoardIds.CYTON_BOARD.value
            elif board_type == 'Ganglion':
                openbci_params.serial_port = self.config.get('serial_port', openbci_port)
                board_id = BoardIds.GANGLION_BOARD.value
            elif board_type == 'Synthetic':
                board_id = BoardIds.SYNTHETIC_BOARD.value
            else:
                raise ValueError("Invalid board type. Must be 'Cyton', 'Ganglion', 'Synthetic'.")
            self.board = BoardShim(board_id, openbci_params)
            self.board.prepare_session()
            self.board.start_stream()
            self.sample_rate = BoardShim.get_sampling_rate(board_id)
            self.n_channels = BoardShim.get_num_rows(board_id)
            self.channel_names = BoardShim.get_eeg_names(board_id)
            self.logger.info(f"OpenBCI setup complete: Sample rate: {self.sample_rate}, Channels: {self.n_channels}, Channel names: {self.channel_names}")
        except Exception as e:
            self.logger.error(f"Producer: Error setting up OpenBCI: {e}", exc_info=True)


    def start_lsl_stream(self):
        try:
            self.config = self.config_manager.load_config(instance=self)
            lsl_stream_name = self.config.get('lsl_stream_name', 'default_lsl_stream')
            
            stream_info = StreamInfo(lsl_stream_name, 'EEG', self.n_channels, self.sample_rate, 'float32', 'myuid1234')
            
            channels = stream_info.desc().append_child('channels')
            for channel_name in self.channel_names:
                channels.append_child('channel').append_child_value('label', channel_name)
            self.stream_outlet = StreamOutlet(stream_info)
            self.logger.info(f"Producer: created LSL data stream outlet:\n"
                             f"  Stream name: {stream_info.name()}\n"
                             f"  Stream type: {stream_info.type()}\n"
                             f"  Number of channels: {stream_info.channel_count()}\n"
                             f"  Sample rate: {stream_info.nominal_srate()}\n"
                             f"  Channel format: {stream_info.channel_format()}\n"
                             f"  Unique identifier: {stream_info.uid()}\n"
                             f"  Channel names: {self.channel_names}")
            self.config_manager.save_config({'channel_names': ','.join(self.channel_names)})
        except Exception as e:
            self.logger.error(f"Producer: Error starting LSL stream: {e}", exc_info=True)


    def push_data_to_lsl(self, data):
        try:
            current_time = time.perf_counter()
            self.stream_outlet.push_chunk(data, timestamp=current_time)
        except Exception as e:
            self.logger.error(f"Producer: Error pushing data to LSL: {e}", exc_info=True)


    def send_data_loop(self):
        if self.mode == "Simulator":
            self.logger.info("Producer: Simulation data loop started...")
            chunk_size = 10
            interval = chunk_size / self.sample_rate
            chunk_length = int(self.sample_rate * interval)
            total_rows = len(self.data)
            last_time = time.perf_counter()
            start_idx = 0
            while True:
                try:
                    current_time = time.perf_counter()
                    if current_time - last_time >= interval:
                        end_idx = start_idx + chunk_length
                        if end_idx > total_rows:
                            end_idx = end_idx % total_rows
                            chunks = np.concatenate((self.data[start_idx:], self.data[:end_idx]), axis=0)
                        else:
                            chunks = self.data[start_idx:end_idx]
                        flat_chunk = chunks.flatten().tolist()
                        self.push_data_to_lsl([flat_chunk])
                        last_time = current_time
                        start_idx = end_idx % total_rows
                    time.sleep(0.00001)
                except Exception as e:
                    self.logger.error(f"Producer: Error in simulation data loop: {e}", exc_info=True)

        elif self.mode == "Brainvision":
            self.logger.info("Producer: Brainvision data loop started...")
            lastBlock = -1
            while True:
                try:
                    data, lastBlock = self.get_data_chunk(self.n_channels, lastBlock)
                    if data:
                        self.push_data_to_lsl(data)
                    time.sleep(0.000001)
                except Exception as e:
                    self.logger.error(f"Producer: Error in Brainvision data loop: {e}", exc_info=True)

        elif self.mode == "OpenBCI":
            self.logger.info("Producer: OpenBCI data loop started...")
            while True:
                try:
                    data = self.board.get_board_data()
                    if data.shape[1] > 0:
                        self.stream_outlet.push_chunk(data.tolist())
                    time.sleep(0.000001)
                except Exception as e:
                    self.logger.error(f"Producer: Error in OpenBCI data loop: {e}", exc_info=True)


    def run(self):
        self.logger.info(f"Producer: started. mode is {self.mode}")
        try:
            if self.mode == "customlsl":
                self.logger.info("Producer: Attempting to connect to custom LSL stream...")
                return
            
            if self.mode == "Simulator":
                self.logger.info("Producer: Attempting to load edf for simulation...")
                self.load_edf_data()
            elif self.mode == "Brainvision":
                self.logger.info("Producer: Attempting to connect to Brainvision amp...")
                self.connect_brainvision_rda()
                self.n_channels, self.sample_rate, resolutions, self.channelnames = self.get_amp_info()
            elif self.mode == "OpenBCI":
                self.logger.info("Producer: Attempting to connect to OpenBCI board...")
                self.setup_openbci()

            self.start_lsl_stream()
            time.sleep(1)
            self.send_data_loop()
        except Exception as e:
            self.logger.error(f"Producer: Error during run: {e}", exc_info=True)
            self.shutdown()
            raise

    def shutdown(self):
        self.logger.info("Producer: shutting down...")
        try:
            if hasattr(self, 'stream_outlet'):
                del self.stream_outlet
                self.logger.info("Producer: LSL outlet deleted...")
            self.logger.info("Producer: LSL stream closed via shutdown")
            if self.mode == "brainvision" and hasattr(self, 'con'):
                self.con.close()
                self.logger.info("Producer: BrainVision RDA connection closed")
            if self.mode == "OpenBCI" and hasattr(self, 'board'):
                self.board.stop_stream()
                self.board.release_session()
                self.logger.info("Producer: OpenBCI session closed")
        except Exception as e:
            self.logger.error(f"Producer: Error during shutdown: {e}", exc_info=True)
