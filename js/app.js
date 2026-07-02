
const CONTRACT = "GUdYAzh14TQcwUSBw79rnFJHZCv64fugTEsq1etDpump";

function copyContract() {
  navigator.clipboard.writeText(CONTRACT).then(() => {
    showToast("CA copied");
  }).catch(() => {
    showToast(CONTRACT);
  });
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

const navbar = document.getElementById("navbar");
window.addEventListener("scroll", () => {
  navbar.classList.toggle("scrolled", window.scrollY > 40);
});

const menuToggle = document.getElementById("menuToggle");
const mobileNav = document.getElementById("mobileNav");

if (menuToggle && mobileNav) {
  menuToggle.addEventListener("click", () => {
    mobileNav.classList.toggle("open");
    document.body.classList.toggle("menu-open");
  });

  mobileNav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      mobileNav.classList.remove("open");
      document.body.classList.remove("menu-open");
    });
  });
}

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
    }
  });
}, { threshold: 0.13 });

document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
