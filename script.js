const CONTRACT = "GUdYAzh14TQcwUSBw79rnFJHZCv64fugTEsq1etDpump";

function copyContract() {
  navigator.clipboard.writeText(CONTRACT).then(() => {
    showToast("Contract copied");
  }).catch(() => {
    showToast(CONTRACT);
  });
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");

  setTimeout(() => {
    toast.classList.remove("show");
  }, 2200);
}

const nav = document.getElementById("nav");
window.addEventListener("scroll", () => {
  nav.classList.toggle("scrolled", window.scrollY > 40);
});

const menuButton = document.getElementById("menuButton");
const mobileMenu = document.getElementById("mobileMenu");

menuButton.addEventListener("click", () => {
  mobileMenu.classList.toggle("open");
  document.body.classList.toggle("menu-open");
});

mobileMenu.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    mobileMenu.classList.remove("open");
    document.body.classList.remove("menu-open");
  });
});

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
    }
  });
}, { threshold: 0.13 });

document.querySelectorAll(".reveal").forEach((element) => {
  observer.observe(element);
});
