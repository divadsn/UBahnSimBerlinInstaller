'use strict';

const versionCode = 4;

// Flags storing check results
let updateAvailable = false;
let isNvidiaGPU = false;

// Object containing additional options for the installation
const additionalOptions = {};

function showMainPage() {
    pywebview.api.isInstalled().then(function(response) {
        $('#main').load(response ? '/views/installed.html' : '/views/landing.html', function() {
            $('#menu').removeClass('d-none');

            // Show update modal if there is a new version
            if (updateAvailable) {
                $("#updateModal").modal("show");
            }
        });
    });
}

function showInstall() {
    $('#main').load('/views/install.html', function() {
        // Check if the user has an existing Trainz installation
        pywebview.api.findInstallPath().then(function(response) {
            if (response) {
                $('#installPath').val(response);
            }
        });

        // Add event listener to the select install path button
        $('#selectInstallPath').on('click', function() {
            const inputField = document.getElementById('installPath');
            pywebview.api.selectInstallPath(inputField.value).then(function(response) {
                if (response) {
                    inputField.setCustomValidity('');
                    inputField.value = response;
                }
            });
        });

        // Reset custom validity on input change
        $('#installPath').on('input', function() {
            this.setCustomValidity('');
        });

        // Start the installation process when the nvidia warning modal is closed
        $('#nvidiaWarningModal').on('hidden.bs.modal', function() {
            startInstall();
        });

        // Bind the form submit event
        $('#installForm').on('submit', function(e) {
            e.preventDefault();

            // Validate the install path
            const installPathField = document.getElementById('installPath');
            const installPath = installPathField.value;

            pywebview.api.validateInstallPath(installPath, true).then(function(response) {
                if (!response) {
                    installPathField.setCustomValidity('Der angegebene Pfad ist ungültig.');
                    installPathField.reportValidity();
                    return;
                }

                if (isNvidiaGPU) {
                    $('#nvidiaWarningModal').modal('show');
                    return;
                }

                startInstall();
            });
        });

        // Save additional options when form is submitted
        $('#additionalOptionsForm').on('submit', function(e) {
            e.preventDefault();

            // Hide the modal
            $('#additionalOptionsModal').modal('hide');

            // Iterate over all input fields with name attribute
            $('#additionalOptionsForm input[name]').each(function() {
                const optionName = $(this).attr('name');

                if (this.type === 'checkbox') {
                    if (this.checked) {
                        additionalOptions[optionName] = true;
                    } else {
                        delete additionalOptions[optionName];
                    }
                } else if (this.type === 'number' && !this.disabled) {
                    additionalOptions[optionName] = parseInt(this.value);
                } else {
                    delete additionalOptions[optionName];
                }
            });
        });
    });
}

function showError(type, title, details) {
    pywebview.api.setConfirmClose(false);
    $('#main').load(`/views/errors/${type}.html`, function() {
        $('#menu').addClass('d-none');

        // Play success sound
        if (type === "success" || type === "warning") {
            new Audio('/static/sounds/complete.wav').play();
        }

        $('#errorTitle').text(title);
        $('#errorDetails').html(details.replaceAll("\n", "<br>"));
    });
}

function checkForUpdates() {
    $('#menu').addClass('d-none');
    $('#main').load('/views/update/check.html', function() {
        setTimeout(function() {
            // Check for new updates
            pywebview.api.checkForUpdates().then(function(response) {
                if (response) {
                    // Show available updates page
                    $('#main').load('/views/update/available.html', function() {
                        $('#lastRevision').text(response);
                    });
                } else {
                    showError("success", "Keine Updates verfügbar", "Deine Installation von U-Bahn Sim Berlin ist auf dem neuesten Stand.");
                }
            }).catch(function(response) {
                showError("nointernet", "Keine Internetverbindung", "Bitte überprüfe deine Internetverbindung und versuche es erneut.");
            });
        }, 1000);
    });
}

function startInstall() {
    const installForm = document.getElementById('installForm');

    // Validate install form
    if (!installForm.checkValidity()) {
        installForm.reportValidity();
        return;
    }

    const installPath = $('#installPath').val();
    const downloadVersion = $('input[name=downloadVersion]:checked').val();

    // Start the installation process
    pywebview.api.startInstall(installPath, downloadVersion, additionalOptions).then(function(response) {
        $('#main').load('/views/progress.html', function() {
            $('#menu').addClass('d-none');
            updateProgress("Installation wird vorbereitet...", 100, "", true, "primary");
        });
    });
}

function startUpdate() {
    // Start the update process
    pywebview.api.startUpdate().then(function(response) {
        $('#main').load('/views/progress.html', function() {
            $('#menu').addClass('d-none');
            updateProgress("Installation wird vorbereitet...", 100, "", true, "primary");
        });
    });
}

function updateProgress(text, progressWidth = null, progressLabel = null, intermediate = null, color = null) {
    // Hide progress bar if text is null
    if (text === null) {
        $('#progress').removeClass('d-flex').addClass('d-none');
        return;
    }

    $('#progress p').text(text);

    // Update progress bar width
    if (progressWidth !== null) {
        $('#progress .progress-bar').css('width', progressWidth.toFixed(2) + '%');
    }

    // Update progress label if available
    if (progressLabel !== null) {
        $('#progress span').text(progressLabel);
    }

    // Set intermediate progress bar
    if (intermediate !== null) {
        if (intermediate) {
            $('#progress .progress-bar').addClass('progress-bar-striped progress-bar-animated');
        } else {
            $('#progress .progress-bar').removeClass('progress-bar-striped progress-bar-animated');
        }
    }

    // Set color if available
    if (color !== null) {
        $('#progress .progress-bar').removeClass((index, className) => (className.match(/(^|\s)bg-\S+/g) || []).join(' ')).addClass(`bg-${color}`);
    }

    $('#progress').removeClass('d-none').addClass('d-flex');
}

function updateExtraProgress(text, progressWidth = null, progressLabel = null) {
    // Hide extra progress bar if text is null
    if (text === null) {
        $('#extraProgress').removeClass('d-flex').addClass('d-none');
        return;
    }

    $('#extraProgress p').text(text);

    // Update progress bar width
    if (progressWidth !== null) {
        $('#extraProgress .progress-bar').css('width', progressWidth.toFixed(2) + '%');
    }

    // Update progress label if available
    if (progressLabel !== null) {
        $('#extraProgress span').text(progressLabel);
    }

    $('#extraProgress').removeClass('d-none').addClass('d-flex');
}

function openContentManager(closeWindow) {
    pywebview.api.openContentManager().then(function() {
        if (closeWindow) {
            pywebview.api.close();
        }
    });
}

function openTrainz() {
    pywebview.api.openTrainz().then(function() {
        pywebview.api.close();
    });
}

//*************************
// Main entry point
//*************************
window.addEventListener('pywebviewready', function() {
    // Check for installer updates
    $.getJSON("https://dl.u7-trainz.de/installer.json", function (data) {
        $("#updateVersion").text(`v${data.versionName}`);
        $("#updateModal .btn-primary").prop("href", data.downloadUrl);

        // Set the updateAvailable flag if there is a new version
        if (data.version > versionCode) {
            updateAvailable = true;
        }

        // Check if Trainz or Content Manager is running
        pywebview.api.isTrainzRunning().then(function(response) {
            // Show error if Trainz is running
            if (response) {
                showError("trainzrunning", "Trainz Simulator läuft bereits", "Bitte schließe Trainz oder den Content Manager und versuche es erneut.");
                return;
            }

            // Check if the user has an Nvidia GPU
            pywebview.api.isNvidiaGPU().then(function(response) {
                // Set the isNvidiaGPU flag
                isNvidiaGPU = response;

                // Check if installation has been aborted
                pywebview.api.isInstallationAborted().then(function (response) {
                    if (response) {
                        $("#main").load("/views/resume.html");
                        return;
                    }

                    showMainPage();
                });
            });
        });
    }).fail(function () {
        // Show error if there is no internet connection
        showError("nointernet", "Keine Internetverbindung", "Bitte überprüfe deine Internetverbindung und versuche es erneut.");
    });
});
