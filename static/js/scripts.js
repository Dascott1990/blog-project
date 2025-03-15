/*!
* Start Bootstrap - Clean Blog v6.0.9 (https://startbootstrap.com/theme/clean-blog)
* Copyright 2013-2023 Start Bootstrap
* Licensed under MIT (https://github.com/StartBootstrap/startbootstrap-clean-blog/blob/master/LICENSE)
*/
document.addEventListener("DOMContentLoaded", () => {
    let scrollPos = 0;
    const mainNav = document.getElementById("mainNav");
    const headerHeight = mainNav ? mainNav.clientHeight : 0;

    window.addEventListener("scroll", function () {
        const currentTop = document.body.getBoundingClientRect().top * -1;
        if (currentTop < scrollPos) {
            // Scrolling Up
            if (currentTop > 0 && mainNav.classList.contains("is-fixed")) {
                mainNav.classList.add("is-visible");
            } else {
                mainNav.classList.remove("is-visible", "is-fixed");
            }
        } else {
            // Scrolling Down
            mainNav.classList.remove("is-visible");
            if (currentTop > headerHeight && !mainNav.classList.contains("is-fixed")) {
                mainNav.classList.add("is-fixed");
            }
        }
        scrollPos = currentTop;
    });

    // Initialize Bootstrap Tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll("[data-bs-toggle='tooltip']"));
    tooltipTriggerList.map((tooltipTriggerEl) => new bootstrap.Tooltip(tooltipTriggerEl));

    // Load Theme from LocalStorage
    const savedTheme = localStorage.getItem("theme") || "light";
    const htmlElement = document.documentElement;
    const themeIcon = document.getElementById("theme-icon");
    const themeToggleBtn = document.getElementById("theme-toggle");

    htmlElement.setAttribute("data-bs-theme", savedTheme);
    if (themeIcon) {
        themeIcon.classList.remove("fa-sun", "fa-moon");
        themeIcon.classList.add(savedTheme === "dark" ? "fa-sun" : "fa-moon");
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener("click", function () {
            toggleDarkMode();
        });
    }
});

function toggleMenu() {
    document.getElementById("profile-menu").classList.toggle("d-none");
}

// Dark Mode Toggle Function
function toggleDarkMode() {
    const htmlElement = document.documentElement;
    const themeIcon = document.getElementById("theme-icon");

    if (htmlElement.getAttribute("data-bs-theme") === "dark") {
        htmlElement.setAttribute("data-bs-theme", "light");
        localStorage.setItem("theme", "light");
        themeIcon.classList.replace("fa-sun", "fa-moon");
    } else {
        htmlElement.setAttribute("data-bs-theme", "dark");
        localStorage.setItem("theme", "dark");
        themeIcon.classList.replace("fa-moon", "fa-sun");
    }
}
