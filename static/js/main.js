// Daily tracking AJAX logic for user dashboard
document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("tracking-form");
    if (!form) {
        // Not on user dashboard, nothing to do
        return;
    }

    const waterCb = document.getElementById("water_completed");
    const foodCb = document.getElementById("food_completed");
    const workoutCb = document.getElementById("workout_completed");
    const challengeCb = document.getElementById("challenge_completed");
    const progressBar = document.getElementById("progress-bar");
    const trackingMessage = document.getElementById("tracking-message");

    function sendUpdate() {
        const payload = {
            water_completed: waterCb.checked,
            food_completed: foodCb.checked,
            workout_completed: workoutCb.checked,
            challenge_completed: challengeCb.checked
        };

        fetch("/user/daily-tracking", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        })
            .then(resp => resp.json())
            .then(data => {
                if (data && data.success) {
                    const progress = data.progress;
                    progressBar.style.width = progress + "%";
                    progressBar.textContent = progress + "%";
                    trackingMessage.textContent = data.message;
                }
            })
            .catch(err => {
                console.error("Tracking update failed", err);
            });
    }

    function updateChallengeDisabled() {
        const allThreeCompleted = waterCb.checked && foodCb.checked && workoutCb.checked;
        challengeCb.disabled = !allThreeCompleted;
        if (!allThreeCompleted) {
            challengeCb.checked = false; // Uncheck if disabling
        }
    }

    [waterCb, foodCb, workoutCb].forEach(cb => {
        if (cb) {
            cb.addEventListener("change", function() {
                updateChallengeDisabled();
                sendUpdate();
            });
        }
    });

    challengeCb.addEventListener("change", sendUpdate);

    // Initial check
    updateChallengeDisabled();
});

// Reminder notifications for the coaching flow
(function () {
    const reminderMessages = [
        "Time to drink water 💧",
        "Time for workout 🏃",
        "Stay healthy! Keep going 💪",
    ];

    function showReminder() {
        const message = reminderMessages[Math.floor(Math.random() * reminderMessages.length)];
        if (window.Notification && Notification.permission === "granted") {
            new Notification("Health Reminder", {
                body: message,
                icon: "https://img.icons8.com/color/48/000000/heart-health.png",
            });
            return;
        }

        if (window.Notification && Notification.permission !== "denied") {
            Notification.requestPermission().then(permission => {
                if (permission === "granted") {
                    new Notification("Health Reminder", { body: message });
                } else {
                    alert(message);
                }
            });
            return;
        }

        alert(message);
    }

    window.addEventListener("load", function () {
        showReminder();
        setInterval(showReminder, 2 * 60 * 1000);
    });
})();

