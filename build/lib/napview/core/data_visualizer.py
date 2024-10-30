from flask import Flask, render_template, jsonify, request
import os
import json
import webbrowser

try:
    from helpers import configure_logger, ConfigManager
except:
    from .helpers import configure_logger, ConfigManager


class Visualizer:
    # Define desired fields as class-level constants
    STAGING_DESIRED_FIELDS = ['n1', 'n2', 'n3', 'rem', 'w']
    YASA_DESIRED_FIELDS = ['alpha_power', 'beta_power', 'theta_power', 'delta_power', 'gamma_power']

    def __init__(self, base_path, mode):
        self.base_path = base_path
        self.app = Flask(__name__)
        self.setup_routes()

        # setup logging
        self.logger = configure_logger(base_path)
        self.logger.info('Visualizer: started...')

        # load variables from config.json
        self.config_manager = ConfigManager(base_path)
        self.config = self.config_manager.load_config(instance=self)

        # Initialize DataLoader objects once with explicit desired fields
        staging_file_path = os.path.join(self.base_path, "data", "results", "staging_results.txt")
        self.staging_data_loader = DataLoader(staging_file_path, self.STAGING_DESIRED_FIELDS, base_path)

        yasa_file_path = os.path.join(self.base_path, "data", "results", "yasa_results.txt")
        self.yasa_data_loader = DataLoader(yasa_file_path, self.YASA_DESIRED_FIELDS, base_path)

    def setup_routes(self):
        @self.app.route('/')
        def home():
            try:
                return render_template('index.html')
            except Exception as e:
                self.logger.error(f"Error rendering template 'index.html': {e}", exc_info=True)
                return "An error occurred", 500

        @self.app.route('/data1')
        def data1():
            try:
                data = self.staging_data_loader.load_data()
                return jsonify(data)
            except Exception as e:
                self.logger.error(f"Error in /data1 endpoint: {e}", exc_info=True)
                return jsonify({'error': 'An error occurred'}), 500

        @self.app.route('/data2')
        def data2():
            try:
                data = self.yasa_data_loader.load_data()
                return jsonify(data)
            except Exception as e:
                self.logger.error(f"Error in /data2 endpoint: {e}", exc_info=True)
                return jsonify({'error': 'An error occurred'}), 500

    def run(self):
        try:
            webbrowser.open(f"http://127.0.0.1:{self.visualizer_port}", new=2)
            self.app.run(debug=False, port=self.visualizer_port)
        except Exception as e:
            self.logger.error(f"Error running the Visualizer: {e}", exc_info=True)

    def shutdown(self):
        pass


class DataLoader:
    def __init__(self, data_file, desired_fields, base_path):
        self.data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), data_file)
        self.desired_fields = desired_fields
        self.logger = configure_logger(base_path)

    def load_data(self):
        data = {}
        try:
            with open(self.data_file, 'r') as file:
                for line in file:
                    entry = json.loads(line)
                    x = entry['start_time']
                    for field, value in entry.items():
                        if field in self.desired_fields:
                            if field not in data:
                                data[field] = []
                            data[field].append({'x': x, 'y': value})
        except Exception as e:
            #self.logger.error(f"Error loading data from {self.data_file}: {e}", exc_info=True)
            # File does not exist, generate one minute of null data
            for field in self.desired_fields:
                data[field] = [{'x': x, 'y': 0} for x in range(0, 60)]
        return data