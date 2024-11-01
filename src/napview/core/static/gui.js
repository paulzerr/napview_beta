(function() {
  // DOM Elements
  const elements = {
    startButton: document.getElementById('startButton'),
    shutdownAndSaveButton: document.getElementById('shutdownAndSaveButton'),
    eeg_amp: document.getElementById('eeg_amp'),
    sleep_staging_model: document.getElementById('sleep_staging_model'),
    settingsButton: document.getElementById('settingsButton'),
    channelConfigButton: document.getElementById('channelConfigButton'),
    ipControl: document.getElementById('ipControl'),
    amp_ip: document.getElementById('amp_ip'),
    loadEegControl: document.getElementById('loadEegControl'),
    loadEegButton: document.getElementById('loadEegButton'),
    sim_input_file_path: document.getElementById('sim_input_file_path'),
    fileInput: document.getElementById('fileInput'),
    apiTokenControl: document.getElementById('apiTokenControl'),
    apiTokenButton: document.getElementById('apiTokenButton'),
    statusLabel: document.getElementById('statusLabel'),
    channelConfigDialog: document.getElementById('channelConfigDialog'),
    channelConfigStatus: document.getElementById('channelConfigStatus'),
    channelList: document.getElementById('channelList'),
    saveChannelConfig: document.getElementById('saveChannelConfig'),
    boardTypeControl: document.getElementById('boardTypeControl'),
    board_type: document.getElementById('board_type'),
    portControl: document.getElementById('portControl'),
    openbci_port: document.getElementById('openbci_port'),
    boardTypeDescription: document.getElementById('boardTypeDescription'),
    lslControl: document.getElementById('lslControl'),
    lsl_stream_name: document.getElementById('lsl_stream_name'),
    record_name: document.getElementById('record_name'),
  };

  const state = {
    api_token: null,
    api_token_valid: false,
    eeg_file_valid: null,
    amp_port: 51244,
    epoch_length: 5,
    base_path: '',
    connection_good: true,
    startAnimationInterval: null,
  };

  async function loadConfig() {
    try {
      const response = await fetch('/load_config');
      const config = await response.json();

      Object.keys(config).forEach((key) => {
        const element = document.getElementById(key);
        if (element) {
          if (element.type === 'checkbox') {
              element.checked = config[key];
          } else {
              element.value = config[key];
          }
        } else {
            state[key] = config[key];
        }
      });

      if (config.app_running) {
        elements.startButton.disabled = true;
      } else {
        elements.startButton.disabled = false;
      }

      // state.api_token_valid = config.api_token_valid || false;
      // state.eeg_file_valid = config.eeg_file_valid || false;

      updateControlsVisibility();
      
    } catch (error) {
        console.error('Error loading config:', error);
    }
  }

  async function updateConfig(data) {
    try {
      console.log('Updating config with data:', data);
      const response = await fetch('/update_config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await response.json();
      if (result.status === 'Configuration updated') {
        await loadConfig();
      }
    } catch (error) {
      console.error('Error updating config:', error);
    }
  }




  function updateStatusText(newMessage = '') {
    loadConfig();
    const statusSnippets = [];

    statusSnippets.push("");


    if (newMessage) {
      statusSnippets.push(newMessage);
    }

    statusSnippets.push(`3Data directory location: <span class='green'>${state.base_path}</span>`);

    if (!elements.eeg_amp.value) {
      statusSnippets.push("Data source: <span class='red'>Please select an amp (or simulator)</span>");
    } else {
      switch (elements.eeg_amp.value) {
        case 'Simulator':
          if (state.eeg_file_valid) {
            statusSnippets.push(
              "Data source: <span class='green'>Playback recording</span> [<span class='green'>Selected EEG file is valid</span>]"
            );
          } else {
            statusSnippets.push(
              "Data source: <span class='green'>Playback recording</span> [<span class='red'>Please select a valid EEG file (.edf)</span>]"
            );
          }
          break;
        case 'Brainvision':
          statusSnippets.push(
                "Data source: <span class='green'>Brainvision</span>"
              );

          // if (elements.amp_ip.value) {
          //   statusSnippets.push(
          //     "Amplifier: <span class='green'>Brainvision</span> [<span class='green'>IP is correct</span>]"
          //   );
          // } else {
          //   statusSnippets.push(
          //     "Amplifier: <span class='red'>Brainvision</span> [<span class='red'>Please enter the correct data acquisition computer IP</span>]"
          //   );
          // }

          break;
        case 'OpenBCI':
          let boardTypeStatus = elements.board_type.value ? `<span class='green'>${elements.board_type.value}</span>` : "<span class='red'>Please select a board type</span>";
          let portStatus = "";
          if (elements.board_type.value === 'Cyton' || elements.board_type.value === 'Ganglion') {
            portStatus = elements.openbci_port.value ? `<span class='green'>Port: ${elements.openbci_port.value}</span>` : "<span class='red'>Please enter a valid port</span>";
          }
          statusSnippets.push(`Data source: <span class='green'>OpenBCI</span> [${boardTypeStatus}] [${portStatus}]`);
          break;
        case 'customlsl':
          if (elements.lsl_stream_name.value) {
            statusSnippets.push(
              `Data source: <span class='green'>Custom LSL</span> [<span class='green'>Stream Name: ${elements.lsl_stream_name.value}</span>]`
            );
          } else {
            statusSnippets.push(
              "Data source: <span class='red'>Custom LSL</span> [<span class='red'>Please enter a valid LSL stream name</span>]"
            );
          }
          break;
        case 'Zmax':
          statusSnippets.push(
            "Data source: <span class='red'>Zmax EEG headband</span> [<span class='red'>This option is currently not implemented</span>]"
          );
          break;
        default:
          break;
      }
    }

    if (!elements.sleep_staging_model.value) {
      statusSnippets.push("Sleep scoring model: <span class='red'>Please select a Sleep Staging Model</span>");
    } else if (elements.sleep_staging_model.value === 'U-Sleep') {
      if (state.api_token_valid) {
        statusSnippets.push(
          "Sleep scoring model: <span class='green'>U-Sleep</span> [<span class='green'>U-Sleep API token is valid</span>]"
        );
      } else {
        statusSnippets.push(
          "Sleep scoring model: <span class='green'>U-Sleep</span> [<span class='red'>Enter a valid U-Sleep API token</span>]"
        );
      }
    } else {
      statusSnippets.push(`Sleep scoring model: <span class='green'>${elements.sleep_staging_model.value}</span>`);
    }

    statusSnippets.push("<br><br>");



    elements.statusLabel.innerHTML = statusSnippets.join('<br><br>');
  }




  function updateControlsVisibility() {
    if (elements.eeg_amp.value === 'Brainvision') {
      elements.ipControl.style.display = 'flex';
    } else {
      elements.ipControl.style.display = 'none';
    }

    if (elements.eeg_amp.value === 'Simulator') {
      elements.loadEegControl.style.display = 'flex';
    } else {
      elements.loadEegControl.style.display = 'none';
    }

    if (elements.eeg_amp.value === 'OpenBCI') {
      elements.boardTypeControl.style.display = 'flex';
      if (elements.board_type.value === 'Cyton' || elements.board_type.value === 'Ganglion') {
        elements.portControl.style.display = 'flex';
      } else {
        elements.portControl.style.display = 'none';
      }
    } else {
      elements.boardTypeControl.style.display = 'none';
      elements.portControl.style.display = 'none'; 
    }

    if (elements.eeg_amp.value === 'customlsl') {
      elements.lslControl.style.display = 'flex';
    } else {
      elements.lslControl.style.display = 'none';
    }

    if (elements.sleep_staging_model.value === 'U-Sleep') {
      elements.apiTokenControl.style.display = 'block';
    } else {
      elements.apiTokenControl.style.display = 'none';
    }

    updateBoardTypeDescription();
  }

  function updateBoardTypeDescription() { 
    if (elements.eeg_amp.value === 'OpenBCI') {
      const descriptions = {
        Cyton: "Enter the port. Typically something like COM3 on Windows, or /dev/ttyUSB0 on Linux.",
        Ganglion: "Enter the port. Typically something like COM3 on Windows, or /dev/ttyUSB0 on Linux.",
        Synthetic: "Simulate an OpenBCI board using synthetic data.",
      };
      elements.boardTypeDescription.textContent = descriptions[elements.board_type.value] || "";
    } else {
      elements.boardTypeDescription.textContent = "";
    }
  }
  

  function openFileDialog() {
    elements.fileInput.click();
  }

  elements.fileInput.addEventListener('change', function () {
    if (elements.fileInput.files.length > 0) {
        const file = elements.fileInput.files[0];
        elements.sim_input_file_path.value = file.name;

        const formData = new FormData();
        formData.append('eegFile', file);

        fetch('/upload_eeg_file', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                console.log('File uploaded successfully');
                updateConfig({ sim_input_file_path: elements.sim_input_file_path.value });
                
              } else {
                console.error('File upload failed:', data.message);
                alert(`Copying the file failed: ${data.message}. You can copy the file to the napview directory manually. Rename to "uploaded_eeg.edf".`); 
            }
        })
        .catch(error => {
            console.error('Error uploading file:', error);
            alert(`Copying the file failed: ${data.message}. You can copy the file to the data directory manually. Rename to "eeg.edf" and click CONNECT.`); 
            
        });
    }
    updateStatusText();
  });


  async function shutdownAndSave() {
    let customMessage = '';
    try {
      const response = await fetch('/shutdown_and_save', {
        method: 'POST',
      });
      const result = await response.json();

      if (result.status === 'success') {
        customMessage = "<span class='green'>Application shutdown and recordings saved successfully.</span><br><br>";
      } else if (result.status === 'partial_success') {
        customMessage = "<span class='orange'>Application shutdown with some issues:</span><br><br>";
        result.messages.forEach((msg) => {
          customMessage += `<span class='orange'>- ${msg}</span><br>`;
        });
        customMessage += "<br>";
      } else if (result.status === 'error') {
        customMessage = "<span class='red'>An error occurred during shutdown:</span><br><br>";
        result.messages.forEach((msg) => {
          customMessage += `<span class='red'>- ${msg}</span><br>`;
        });
        customMessage += "<br>";
      } else {
        customMessage = "<span class='red'>An unknown error occurred. Please try again.</span><br><br>";
      }

      elements.startButton.disabled = false;
    } catch (error) {
      console.error('Error shutting down and saving recordings:', error);
      customMessage = "<span class='red'>An error occurred while shutting down and saving recordings. Please try again.</span><br><br>";
      elements.startButton.disabled = false;
    }
    updateStatusText(customMessage);
  }

  function showApiTokenDialog() {
    const token = prompt('Enter the U-Sleep API token:', state.api_token || '');
    if (token !== null) {
      state.api_token = token;
      updateConfig({ api_token: token });
    }
    updateStatusText();
  }

  function showSettingsDialog() {
    const epochLengthInput = prompt('Enter the epoch length (in seconds):', state.epoch_length);
    if (epochLengthInput !== null) {
      state.epoch_length = parseInt(epochLengthInput);
      updateConfig({ epoch_length: state.epoch_length });
    }
    updateStatusText();
  }

  async function startApplication() {
    let customMessage = '';
    elements.startButton.disabled = true;
    try {
        const response = await fetch('/start', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.status === 'error') {

            switch (result.message) {
                case 'Invalid API token':
                    customMessage = "<span class='red'>The API token provided is invalid. Please check and try again.</span><br><br>";
                    break;
                case 'Invalid EEG file':
                    customMessage = "<span class='red'>The EEG file is invalid. Please upload a valid file (.edf).</span><br><br>";
                    break;
                case 'A process is already running':
                    customMessage = "<span class='red'>A process is already running. Please stop it before starting a new one.</span><br><br>";
                    break;
                case 'Connection failed':
                    customMessage = "<span class='red'>Failed to connect. Please check your configuration and try again.</span><br><br>";
                    break;
                default:
                    customMessage = "<span class='red'>An unknown error occurred. Please try again.</span><br><br>";
            }
        } else if (result.status === 'success') {
            const visualizerUrl = `http://127.0.0.1:${state.visualizer_port}`;
            customMessage = `<span class='green'>Napview is starting in a new tab, otherwise navigate to </span><span class='green'><a href="${visualizerUrl}" target="_blank">${visualizerUrl}</a></span><br><br>`;
        }
        
    } catch (error) {
        console.error('Error starting application:', error);
        customMessage = "<span class='red'>An error occurred while starting the application. Please try again.</span><br><br>" + elements.statusLabel.innerHTML;
        elements.startButton.disabled = false;
      }
    updateStatusText(customMessage);
}

  async function showChannelConfigDialog() {
    elements.channelConfigDialog.style.display = 'flex';
    elements.channelConfigStatus.textContent = 'Connecting to data stream...';

    try {
      const producerResponse = await fetch('/start_data_producer', {
        method: 'POST',
      });
      if (!producerResponse.ok) {
        throw new Error('Failed to start data producer.');
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));

      const channelNames = await fetchChannelNames();
      if (channelNames.length === 0) {
        throw new Error('No channel names retrieved.');
      }

      elements.channelConfigStatus.textContent = 'Retrieved channel names:';
      renderChannelList(channelNames);
    } catch (error) {
      console.error('Error configuring channels:', error);
      elements.channelConfigStatus.textContent =
        'Error retrieving channel names. Please try again.';
    }
  }

  async function fetchChannelNames() {
    const maxRetries = 20;
    const retryDelay = 2000;
    let channelNames = [];
  
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const response = await fetch('/load_config');
        if (response.ok) {
          const config = await response.json();
          if (config.channel_names) {
            if (Array.isArray(config.channel_names)) {
              // If channel_names is already an array, use it directly
              channelNames = config.channel_names;
            } else if (typeof config.channel_names === 'string') {
              // If channel_names is a string, split it into an array
              channelNames = config.channel_names.split(',');
            } else {
              console.error('Unknown format for channel_names:', config.channel_names);
            }
            break;
          }
        }
      } catch (error) {
        console.error('Error fetching channel names:', error);
      }
      // Wait before retrying
      await new Promise((resolve) => setTimeout(resolve, retryDelay));
    }
  
    return channelNames;
  }

  function renderChannelList(channelNames) {
    const tbody = document.createElement('tbody');

    channelNames.forEach((name, index) => {
      const tr = document.createElement('tr');

      const tdNumber = document.createElement('td');
      tdNumber.textContent = index + 1;
      tr.appendChild(tdNumber);

      const tdName = document.createElement('td');
      tdName.textContent = name;
      tr.appendChild(tdName);

      const tdType = document.createElement('td');
      const select = document.createElement('select');
      ['EEG', 'EOG', 'EMG', 'ECG', 'Other'].forEach((optionValue) => {
        const option = document.createElement('option');
        option.value = optionValue.toLowerCase();
        option.textContent = optionValue;
        if (name.toLowerCase().includes(optionValue.toLowerCase())) {
          option.selected = true;
        }
        select.appendChild(option);
      });
      tdType.appendChild(select);
      tr.appendChild(tdType);

      const tdInclude = document.createElement('td');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = true;
      tdInclude.appendChild(checkbox);
      tr.appendChild(tdInclude);

      // Add this block for the preferred YASA channel radio button
      const tdPreferredYasa = document.createElement('td');
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'preferredYasaChannel';
      radio.value = name;
      tdPreferredYasa.appendChild(radio);
      tr.appendChild(tdPreferredYasa);

      tbody.appendChild(tr);
    });

    const table = document.createElement('table');
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    ['Number', 'Name', 'Type', 'Include'].forEach((headerText) => {
      const th = document.createElement('th');
      th.textContent = headerText;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    table.appendChild(thead);
    table.appendChild(tbody);

    elements.channelList.innerHTML = '';
    elements.channelList.appendChild(table);
  }

  elements.saveChannelConfig.addEventListener('click', async () => {
    const channelRows = document.querySelectorAll('#channelList tbody tr');
    const channelTypes = [];
    const channelIncludes = [];
    let preferredYasaChannel = null;

    channelRows.forEach((row) => {
        const type = row.children[2].querySelector('select').value;
        const include = row.children[3].querySelector('input').checked;
        const radio = row.children[4].querySelector('input[type="radio"]');

        channelTypes.push(type);
        channelIncludes.push(include ? '1' : '0');

        if (radio.checked) {
          preferredYasaChannel = radio.value;
        }

    });

    const data = {
        channel_types: channelTypes.join(','),
        channel_includes: channelIncludes.join(','),
        preferred_yasa_channel: preferredYasaChannel
    };

    await updateConfig(data);

    // Stop the data producer after saving
    try {
        const response = await fetch('/stop_data_producer', {
            method: 'POST'
        });
        const result = await response.json();
        console.log(result.status);
    } catch (error) {
        console.error('Error stopping data producer:', error);
    }

    elements.channelConfigDialog.style.display = 'none';
  });

  async function check_eeg_file() {
    try {
      const response = await fetch('/check_eeg_file', {
        method: 'POST'
      });
      const result = await response.json();
      updateStatusText()
      // if (result.status === 'success') {
      //   console.log('EEG file is valid');
      //   updateStatusText('EEG file is valid');
      // } else {
      //   console.error('Invalid EEG file:', result.message);
      //   updateStatusText('Invalid EEG file');
      // }
    } catch (error) {
      console.error('Error checking EEG file:', error);
      updateStatusText();
    }
  }

  elements.eeg_amp.addEventListener('change', function () {
      updateConfig({ eeg_amp: elements.eeg_amp.value });
      if (elements.eeg_amp.value === 'Simulator') {
        check_eeg_file();
      }
      updateControlsVisibility();
      updateStatusText();
  });

  elements.sleep_staging_model.addEventListener('change', function () {
      updateConfig({ sleep_staging_model: elements.sleep_staging_model.value });
      // if (elements.sleep_staging_model.value !== 'U-Sleep') {
      //     state.api_token_valid = false;
      // }
      updateControlsVisibility();
      updateStatusText();
  });


  elements.amp_ip.addEventListener('input', function () {
    updateConfig({ amp_ip: elements.amp_ip.value });
    updateStatusText();
  });

  elements.sim_input_file_path.addEventListener('input', function () {
    updateConfig({ sim_input_file_path: elements.sim_input_file_path.value });
    updateStatusText();
  });

  elements.board_type.addEventListener('change', function () {
    updateConfig({ board_type: elements.board_type.value });
    updateControlsVisibility();
    updateStatusText();
  });
  
  elements.openbci_port.addEventListener('input', function () {
    updateConfig({ openbci_port: elements.openbci_port.value });
    updateStatusText();
  });

  elements.lsl_stream_name.addEventListener('input', function () {
    updateConfig({ lsl_stream_name: elements.lsl_stream_name.value });
    updateStatusText();
  });

  // Helper debounce function
  function debounce(func, wait) {
    let timeout;
    return function(...args) {
      const context = this;
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(context, args), wait);
    };
  }
  elements.record_name.addEventListener('input', debounce(function () {
    updateConfig({ record_name: elements.record_name.value });
  }, 500)); // Adjust the delay (in milliseconds) as needed


  // elements.record_name.addEventListener('input', function () {
  //   updateConfig({ record_name: elements.record_name.value });
  // });

  elements.loadEegButton.addEventListener('click', openFileDialog);
  elements.apiTokenButton.addEventListener('click', showApiTokenDialog);
  elements.settingsButton.addEventListener('click', showSettingsDialog);
  elements.channelConfigButton.addEventListener('click', showChannelConfigDialog);
  elements.startButton.addEventListener('click', startApplication);
  elements.shutdownAndSaveButton.addEventListener('click', shutdownAndSave);

 loadConfig().then(() => {
  if (elements.eeg_amp.value === 'Simulator') {
    Promise.all([check_eeg_file(),      ]).then(() => {
      loadConfig().then(() => {
        updateStatusText();
      });
    });
  } else {
    updateStatusText();
  }
});


})();
