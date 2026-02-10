const selectBtn = document.getElementById("selectShops");

if (selectBtn) {
  selectBtn.addEventListener("click", () => {
    const inStudent = window.location.pathname.toLowerCase().includes("/student/");
    window.location.href = inStudent ? "shops.html" : "student/shops.html";
  });
}
