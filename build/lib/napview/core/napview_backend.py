import os
import json
import multiprocessing
import webbrowser
from pathlib import Path
import socket 
from http.server import HTTPServer, SimpleHTTPRequestHandler
from usleep_api import USleepAPI
import time 
from pathlib import Path
import mne
import cgi
import shutil
from datetime import datetime, timezone
import threading 

try:
    from data_producer import DataProducer
    from data_recorder import DataRecorder
    from data_analyzer import Analyzer
    from data_visualizer import Visualizer
    from database_handler import DatabaseHandler
    from helpers import configure_logger, ConfigManager
except:
    from .data_producer import DataProducer
    from .data_recorder import DataRecorder
    from .data_analyzer import Analyzer
    from .data_visualizer import Visualizer
    from .database_handler import DatabaseHandler
    from .helpers import configure_logger, ConfigManager


def load_config_defaults(base_path):
    config_json_path = os.path.join(base_path, 'config.json')
    if os.path.exists(config_json_path):
        os.remove(config_json_path)

    config_file_path = os.path.join(base_path, 'CONFIG_DEFAULTS.txt')
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r') as file:
                config_defaults = json.load(file)
                return config_defaults
        except Exception as e:
            raise(e)
    
    return {
        'sim_input_file_path': 'uploaded_eeg.edf',
        'amp_ip': '131.174.45.239',
        'amp_port': 51244,
        'epoch_length': 30,
        'api_token': 'token',
        'eeg_amp': 'Simulator',
        'sleep_staging_model': 'YASA',
        'db_file_path': '',
        'board_type': 'Synthetic',
        'openbci_port': 'COM3',
        "lsl_stream_name": 'napview_EEG_stream'
    }


class ProcessManager:
    def __init__(self):
        self.processes = {}

    @staticmethod
    def run_pipeline_component(component_class, **kwargs):
        component = component_class(**kwargs)
        try:
            component.run()
        finally:
            component.shutdown()

    def start_process(self, role, component_class, **kwargs):
        if self.is_process_running(role):
            print(f"Process {role} is already running.")
            return
        process = multiprocessing.Process(target=self.run_pipeline_component, args=(component_class,), kwargs=kwargs)
        process.start()
        self.processes[role] = process

    def stop_process(self, role):
        process = self.processes.get(role)
        if process and process.is_alive():
            process.terminate()
            process.join()
            del self.processes[role]

    def stop_processes(self):
        for process in self.processes.values():
            if process.is_alive():
                process.terminate()
                process.join()
        self.processes.clear()

    def is_process_running(self, role):
        process = self.processes.get(role)
        return process is not None and process.is_alive()

    def any_process_running(self):
        return any(process.is_alive() for process in self.processes.values())

    def launch_components(self, base_path, config_manager, components):
        with config_manager.config_lock:
            config_manager.load_config(instance=self)
        component_map = {
            'producer': (DataProducer, {'mode': self.config.get('eeg_amp', 'Simulator')}),
            'recorder': (DataRecorder, {'mode': ''}),
            'analyzer1': (Analyzer, {'mode': 'yasa_analyzer'}),
            'analyzer2': (Analyzer, {'mode': self.config.get('sleep_staging_model', 'YASA')}),
            'visualizer': (Visualizer, {'mode': ''})
        }

        for component in components:
            if component in component_map:
                component_class, kwargs = component_map[component]
                kwargs['base_path'] = base_path
                self.start_process(component, component_class, **kwargs)

class NapviewRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, process_manager=None, base_path=None, config_manager=None, db_handler=None, logger=None, **kwargs):
        self.process_manager = process_manager
        self.base_path       = base_path
        self.config_manager  = config_manager
        self.logger          = logger
        self.db_handler      = db_handler
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.path = '/templates/gui.html' 

        elif self.path == '/load_config':
            with self.config_manager.config_lock:
                self.config = self.config_manager.load_config(instance=self)
            self.config['app_running'] = self.process_manager.any_process_running()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(self.config).encode('utf-8'))
            return
        
        try:
            return super().do_GET()
        except BrokenPipeError:
            self.logger.error("BrokenPipeError: Client disconnected before response was fully sent.", exc_info=True)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            
    def do_POST(self):
        try:
            if self.path == '/start':
                ready = True
                self.config = self.config_manager.load_config(instance=self)

                # Check if the API token is valid
                if self.config.get('sleep_staging_model') == 'U-Sleep' and not self.validate_usleep_token():
                    self.logger.error(f"GUI: start_attempt: invalid API token")
                    response = {'status': 'error', 'message': 'Invalid API token'}
                    ready = False

                # Check if the EEG file is valid
                if self.config.get('eeg_amp') == 'Simulator' and not self.validate_eeg_file():
                    self.logger.error(f"GUI: start_attempt: invalid EEG file")
                    response = {'status': 'error', 'message': 'Invalid EEG file'}
                    ready = False

                # Check if any process is already running
                if self.process_manager.any_process_running():
                    self.logger.error(f"GUI: start_attempt: process already running")
                    response = {'status': 'error', 'message': 'A process is already running'}
                    ready = False

                if ready:
                    try:
                        self.process_manager.launch_components(self.base_path, self.config_manager, ['producer', 'recorder'])
                        response = {'status': 'success', 'message': 'Producer and recorder started'}
                    except Exception as e:
                        self.logger.error(f"GUI: Connection failed: {e}", exc_info=True)
                        self.process_manager.stop_processes()
                        response = {'status': 'error', 'message': f'Connection failed: {str(e)}'}
                        ready = False
                if ready:
                    self.process_manager.launch_components(self.base_path, self.config_manager, ['analyzer1', 'analyzer2', 'visualizer'])
                
            elif self.path == '/check_eeg_file':
                self.validate_eeg_file()
                response = {'status': 'eeg file checked'}

            elif self.path == '/start_data_producer':
                if not self.process_manager.is_process_running('producer'):
                    self.process_manager.launch_components(self.base_path, self.config_manager, ['producer'])
                    response = {'status': 'Data producer started'}
                else:
                    response = {'status': 'Data producer already running'}

            elif self.path == '/stop_data_producer':
                self.process_manager.stop_process('producer')
                response = {'status': 'Data producer stopped'}

            elif self.path == '/shutdown_and_save':
                self.config = self.config_manager.load_config(instance=self)
                self.process_manager.stop_processes()
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                output_directory = os.path.join(self.base_path, 'output', timestamp)
                os.makedirs(output_directory, exist_ok=True)
                messages = []

                # Save EEG data
                eeg_result = self.save_eeg_data_as_edf(self.config.get('db_file_path'), output_directory, timestamp)
                messages.append(eeg_result['message'])

                # Save results files
                results_result = self.save_results_files(output_directory, timestamp)
                messages.extend(results_result['messages'])

                # Determine overall success
                if eeg_result['success'] and results_result['success']:
                    response_status = 'success'
                elif not eeg_result['success'] and not results_result['success']:
                    response_status = 'error'
                else:
                    response_status = 'partial_success'

                response = {'status': response_status, 'messages': messages}

                # Clean up data directories
                data_path = os.path.join(self.base_path, "data")
                directories_to_clean = ['db', 'edfs', 'results']
                for dirname in directories_to_clean:
                    dirpath = os.path.join(data_path, dirname)
                    for root, dirs, files in os.walk(dirpath):
                        for file in files:
                            file_path = os.path.join(root, file)
                            os.remove(file_path)
                            self.logger.info(f"Shutdown: Deleted file: {file_path}")

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))

                # Shutdown the server in a separate thread
                shutdown_thread = threading.Thread(target=self.shutdown_server)
                shutdown_thread.start()
                self.logger.info("Server shut down successfully.")
                return

            elif self.path == '/update_config':
                content_length = int(self.headers['Content-Length'])
                config_updates = json.loads(self.rfile.read(content_length).decode('utf-8'))
                with self.config_manager.config_lock:
                    self.config = self.config_manager.load_config(instance=self)
                    self.config.update(config_updates)
                    self.config_manager.save_config(self.config)
                response = {'status': 'Configuration updated'}

            elif self.path == '/upload_eeg_file':
                content_type, pdict = cgi.parse_header(self.headers['Content-Type'])
                if content_type == 'multipart/form-data':
                    pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
                    pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])
                    fields = cgi.parse_multipart(self.rfile, pdict)
                    eeg_file = fields.get('eegFile')

                    if eeg_file:
                        try:
                            file_data = eeg_file[0]
                            disposition_header = self.headers.get('Content-Disposition')
                            if disposition_header:
                                _, params = cgi.parse_header(disposition_header)
                                file_name = params.get('filename')
                            else:
                                file_name = 'eeg.edf'  
                            if not file_name:
                                raise ValueError("Filename not provided in the request")

                            save_path = os.path.join(self.base_path, file_name)
                            with open(save_path, 'wb') as f:
                                f.write(file_data)
                            self.validate_eeg_file()

                            response = {'status': 'success'}
                        except Exception as e:
                            response = {'status': 'error', 'message': str(e)}
                    else:
                        response = {'status': 'error', 'message': 'No file uploaded'}

                else:
                    response = {'status': 'error', 'message': 'Invalid content type'}

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            time.sleep(.1)
            return
        
        except BrokenPipeError:
            self.logger.warning("Client disconnected before response was fully sent.", exc_info=True)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)

    def shutdown_server(self):
        """Shut down the server."""
        self.logger.info("Shutdown: Initiating server shutdown...")
        self.server.shutdown()
        self.server.server_close()
        self.logger.info("Shutdown: Server shut down successfully.")


    def validate_usleep_token(self):
        try:
            self.config = self.config_manager.load_config(instance=self)
            USleepAPI(api_token=self.config['api_token'])
            token_valid = True
            self.logger.info('Init: API token is valid.')
        except Exception as e:
            self.logger.error(f'Init: Failed to validate U-Sleep API token: {e}')
            token_valid = False
        with self.config_manager.config_lock:
            self.config['api_token_valid'] = token_valid
            self.config_manager.save_config(self.config)
        return token_valid
    
    def validate_eeg_file(self):
        try:
            self.config = self.config_manager.load_config(instance=self)
            filename = self.config.get('sim_input_file_path', 'eeg.edf')
            full_path = Path(self.base_path) / filename
            mne.io.read_raw_edf(full_path, preload=False)
            eeg_file_valid = True
            self.logger.info(f"Init: EEG file is valid.")
        except Exception as e:
            self.logger.error(f"Init: Invalid EEG file: {e}", exc_info=True)
            eeg_file_valid = False
        with self.config_manager.config_lock:
            self.config['eeg_file_valid'] = eeg_file_valid
            self.config_manager.save_config(self.config)
        return eeg_file_valid

    def save_eeg_data_as_edf(self, db_file_path, output_directory, timestamp):
        result = {'success': True, 'message': ''}
        try:
            eeg_info = self.db_handler.retrieve_info()
            if eeg_info is None:
                raise ValueError("No EEG information found in the database.")

            total_samples = self.db_handler.get_total_n_samples()
            if total_samples is None or total_samples == 0:
                raise ValueError("No EEG data found in the database.")

            end_sample_index = total_samples - 1
            eeg_data = self.db_handler.retrieve_data(0, end_sample_index)
            if eeg_data is None:
                raise ValueError("Failed to retrieve EEG data.")

            channel_names = eeg_info.channel_names.strip("[]").replace("'", "").replace('"', "")
            channel_names = [name.strip() for name in channel_names.split(',')]

            info = mne.create_info(
                ch_names=channel_names,
                sfreq=eeg_info.sample_rate,
                ch_types=['eeg'] * eeg_info.n_channels  
            )
            raw = mne.io.RawArray(eeg_data, info)
            # TODO: get actual eeg recording time
            raw.set_meas_date(datetime.now(timezone.utc))

            edf_file_path = os.path.join(output_directory, f'recording_{timestamp}.edf')
            mne.export.export_raw(edf_file_path, raw, fmt='edf', overwrite=True)
            self.logger.info(f"Shutdown: EEG data saved to {edf_file_path}")
            result['message'] = f"EEG data saved to {edf_file_path}"

        except ValueError as ve:
            self.logger.warning(f"Shutdown: {str(ve)}")
            result['success'] = False
            result['message'] = str(ve)
        except Exception as e:
            self.logger.error(f"Shutdown: Unexpected error while saving EEG data: {e}", exc_info=True)
            result['success'] = False
            result['message'] = "An error occurred while saving EEG data."

        return result
    
    def save_results_files(self, output_directory, timestamp):
        result = {'success': True, 'messages': []}
        try:
            staging_results_file = os.path.join(self.base_path, 'data', 'results', 'staging_results.txt')
            staging_results_dest = os.path.join(output_directory, f'staging_results_{timestamp}.txt')
            if os.path.exists(staging_results_file):
                shutil.copy2(staging_results_file, staging_results_dest)
                self.logger.info(f"Copied {staging_results_file} to {staging_results_dest}")
                result['messages'].append(f"Staging results saved to {staging_results_dest}")
            else:
                warning_msg = f"Staging results file {staging_results_file} does not exist."
                self.logger.warning(warning_msg)
                result['messages'].append(warning_msg)

            yasa_results_file = os.path.join(self.base_path, 'data', 'results', 'yasa_results.txt')
            yasa_results_dest = os.path.join(output_directory, f'yasa_results_{timestamp}.txt')
            if os.path.exists(yasa_results_file):
                shutil.copy2(yasa_results_file, yasa_results_dest)
                self.logger.info(f"Copied {yasa_results_file} to {yasa_results_dest}")
                result['messages'].append(f"YASA results saved to {yasa_results_dest}")
            else:
                warning_msg = f"YASA results file {yasa_results_file} does not exist."
                self.logger.warning(warning_msg)
                result['messages'].append(warning_msg)

        except Exception as e:
            self.logger.error(f"Shutdown: Unexpected error while saving results files: {e}", exc_info=True)
            result['success'] = False
            result['messages'].append("An error occurred while saving results files.")

        return result

def main():

    # init process manager
    multiprocessing.set_start_method('spawn', True)
    process_manager = ProcessManager()
    
    # setup data path in the user's home directory
    try:
        base_path = Path.home() / "napview"
        base_path.mkdir(parents=True, exist_ok=True)
        #logger.info(f'Init: data dir set up at {base_path}')
    except Exception as e:
        try:
            base_path = Path(__file__).resolve().parent
            #logger.info(f'Init: data dir set up at {base_path}, because home directory setup failed')
        except Exception as e:
            #logger.info(f'Init: data dir setup failed at both local dir and home dir, exiting. Error: {e}')
            raise

    # start logger
    logger = configure_logger(base_path)
    logger.info('')        
    logger.info('')        
    logger.info('Init: #############################################################')        
    logger.warning('Init: #################### New run started ########################')
    logger.info('Init: #############################################################')

    # init central config file + manager
    CONFIG_DEFAULTS = load_config_defaults(base_path)
    config_manager = ConfigManager(base_path, CONFIG_DEFAULTS)
    config_manager.save_config({'base_path': str(base_path)})

    # create data directories 
    try:
        data_path = os.path.join(base_path, "data")
        os.makedirs(data_path, exist_ok=True)
        os.makedirs(os.path.join(data_path, "db"), exist_ok=True)
        os.makedirs(os.path.join(data_path, "results"), exist_ok=True)
        os.makedirs(os.path.join(data_path, "edfs"), exist_ok=True)
        os.makedirs(os.path.join(data_path, "output"), exist_ok=True)
        logger.info(f'Data directories created in {base_path}')
    except Exception as e:
        logger.error(f'Failed to create data directories in {base_path} : {str(e)}', exc_info=True)

    # empty data folders 
    data_path = os.path.join(base_path, "data")
    for root, dirs, files in os.walk(data_path):
        if root == os.path.join(data_path, "db"):
            continue  
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)
            logger.info(f"Init: Deleted file: {file_path}")

    # Check if simulation eeg file exists in base_path, if not, copy it from src/napview
    eeg_file_name = 'eeg.edf'
    src_eeg_file_path = Path(__file__).resolve().parent / 'src/napview' / eeg_file_name
    dest_eeg_file_path = base_path / eeg_file_name

    if not dest_eeg_file_path.exists():
        try:
            shutil.copy(src_eeg_file_path, dest_eeg_file_path)
            logger.info(f"Init: Copied simulation {eeg_file_name} to {base_path}")
        except Exception as e:
            logger.error(f"Init: Failed to copy {eeg_file_name}: {e}", exc_info=True)

    # Check if CONFIG_DEFAULTS.txt exists, if not, create it
    config_defaults_path = os.path.join(base_path, 'CONFIG_DEFAULTS.txt')
    if not os.path.exists(config_defaults_path):
        try:
            with open(config_defaults_path, 'w') as file:
                json.dump(CONFIG_DEFAULTS, file, indent=4)
            logger.info("CONFIG_DEFAULTS.txt created with default values.")
        except Exception as e:
            logger.error(f"Failed to create CONFIG_DEFAULTS.txt: {e}", exc_info=True)

    def find_free_port(start_port,logger):
        for attempt in range(5000):
            port = start_port + attempt
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
        logger.error("Failed to find a free port after 5000 attempts", exc_info=True)
        raise RuntimeError("Unable to find a free port after 5000 attempts")

    # find free ports
    gui_server_port = find_free_port(8145,logger)
    visualizer_port = find_free_port(gui_server_port + 100,logger)
    config_manager.save_config({
        'gui_server_port': gui_server_port,
        'visualizer_port': visualizer_port
    })
    logger.info(f'Init: Ports - - - gui: {gui_server_port},  visualizer: {visualizer_port}')

    # intialize database
    db_handler = DatabaseHandler(base_path)
    db_file_path = db_handler.create_unique_db_filename(f"{base_path}/data/db/eeg_data.db")
    db_handler.setup_database(db_file_path, create_tables=True)
    config_manager.save_config({'db_file_path': db_file_path})

    # init GUI server
    root_dir = Path(__file__).resolve().parent
    gui_server_handler = lambda *args, **kwargs: NapviewRequestHandler(
        *args,
        directory=root_dir,
        process_manager=process_manager,
        base_path=base_path,
        config_manager=config_manager,
        db_handler=db_handler,
        logger=logger,
        **kwargs
    )

    # launch GUI in browser
    httpd = HTTPServer(('localhost', gui_server_port), gui_server_handler)
    print(f"Server started at http://localhost:{gui_server_port}")
    logger.info(f"Server started at http://localhost:{gui_server_port}")
    time.sleep(2)
    webbrowser.open(f"http://localhost:{gui_server_port}", new=1)
    # TODO: open in built-in browser/electron
    try:
        logger.info("GUI: Server starting...")
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("GUI: Server interrupted by user")
    except Exception as e:
        logger.error(f"GUI: An unexpected error occurred: {str(e)}", exc_info=True)
    finally:
        logger.info("GUI: Server shutting down...")
        httpd.shutdown()
        httpd.server_close()
        logger.info("GUI: Server closed successfully")
        process_manager.stop_processes()

if __name__ == "__main__":
    main()

