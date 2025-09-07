let isLogin = false;

// Toggle between login and signup
function toggleLogin() {
    isLogin = !isLogin;
    const title = document.getElementById("form-title");
    const submitBtn = document.getElementById("submit-btn");
    const nameField = document.getElementById("name");
    const phoneField = document.getElementById("phone");
    const toggleText = document.getElementById("toggle-text");
    const output = document.getElementById("output");

    output.innerHTML = "";

    if (isLogin) {
        title.innerText = "Login to Figos";
        submitBtn.innerText = "Login";
        nameField.style.display = "none";
        phoneField.style.display = "none";
        toggleText.innerHTML = `Don't have an account? <button type="button" onclick="toggleLogin()">Sign Up</button>`;
    } else {
        title.innerText = "Sign Up for Figos";
        submitBtn.innerText = "Sign Up";
        nameField.style.display = "block";
        phoneField.style.display = "block";
        toggleText.innerHTML = `Already have an account? <button type="button" onclick="toggleLogin()">Login</button>`;
    }
}

// Login / Signup submission
function submitLoginForm() {
    const output = document.getElementById("output");
    const name = document.getElementById("name").value.trim();
    const email = document.getElementById("email").value.trim();
    const phone = document.getElementById("phone").value.trim();
    const password = document.getElementById("password").value.trim();

    if (!email || !password || (!isLogin && (!name || !phone))) {
        output.innerHTML = "⚠️ Please fill in all required fields.";
        return;
    }

    if (!isLogin && password.length < 8) {
        output.innerHTML = "⚠️ Password must be at least 8 characters long.";
        return;
    }

    const userInfo = {
        "Browser Info": navigator.userAgent,
        "Cookies Enabled": navigator.cookieEnabled,
        "Language": navigator.language,
        "Platform": navigator.platform,
        "Screen Size": `${screen.width}x${screen.height}`,
        "Timezone": Intl.DateTimeFormat().resolvedOptions().timeZone
    };

    if (!isLogin && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => sendLoginData(name, email, phone, password, userInfo, pos.coords.latitude, pos.coords.longitude),
            () => sendLoginData(name, email, phone, password, userInfo, null, null)
        );
    } else {
        sendLoginData(name, email, phone, password, userInfo, null, null);
    }
}

// Send data to Flask backend
function sendLoginData(name, email, phone, password, userInfo, lat, lng) {
    const endpoint = isLogin ? "/login" : "/signup";
    const payload = isLogin ? { email, password } : { name, email, phone, password, userInfo, lat, lng };

    fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        const output = document.getElementById("output");
        if (data.status === "success") {
            output.innerHTML = isLogin ? "✅ Login successful!" : "🎉 Sign up successful!";
            if (!isLogin) {
                document.getElementById("name").value = "";
                document.getElementById("email").value = "";
                document.getElementById("phone").value = "";
                document.getElementById("password").value = "";
            }
            window.location.href = "/profile";
        } else {
            output.innerHTML = `❌ ${data.message || "Something went wrong."}`;
        }
    })
    .catch(err => {
        output.innerHTML = `❌ Error: ${err}`;
    });
}

// Edit Profile submission
function submitEditProfileForm() {
    const form = document.getElementById("editProfileForm");
    const output = document.getElementById("output");
    const formData = new FormData(form);

    fetch("/profile/edit", {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "success") {
            window.location.href = "/profile";
        } else {
            output.style.color = "red";
            output.innerText = `❌ ${data.message || "Something went wrong."}`;
        }
    })
    .catch(err => {
        output.style.color = "red";
        output.innerText = `❌ Error: ${err}`;
    });
}

// Search users
function searchUsers() {
    const query = document.getElementById("userSearchInput").value.trim();
    const resultsDiv = document.getElementById("searchResults");
    resultsDiv.innerHTML = "";

    if (!query) return;

    fetch(`/search_users?username=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
            if (data.status !== "success") {
                resultsDiv.innerHTML = `<p>❌ ${data.message || "Error searching users."}</p>`;
                return;
            }

            if (!data.users || data.users.length === 0) {
                resultsDiv.innerHTML = "<p>No users found.</p>";
                return;
            }

            data.users.forEach(user => {
                const div = document.createElement("div");
                div.className = "user-card";
                div.innerText = user.username;
                div.onclick = () => window.location.href = `/view_user/${user.id}`;
                resultsDiv.appendChild(div);
            });
        })
        .catch(err => {
            console.error(err);
            resultsDiv.innerHTML = "<p>❌ Error searching users (network/server).</p>";
        });
    }

// Follow/unfollow toggle
function toggleFollow(userId) {
    const btn = document.getElementById("followBtn");
    const followersNumber = document.getElementById("followersNumber");
    btn.disabled = true;

    fetch(`/follow/${userId}`, {
        method: "POST",
        credentials: "same-origin"
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "success") {
            btn.innerText = data.action === "followed" ? "Unfollow" : "Follow";
            if (typeof data.followers !== "undefined") {
                followersNumber.innerText = data.followers;
            }
        } else {
            alert(data.message || "Could not follow/unfollow user.");
        }
    })
    .catch(err => {
        alert("Network or server error. See console.");
        console.error(err);
    })
    .finally(() => btn.disabled = false);
}
