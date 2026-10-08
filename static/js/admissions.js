// Keep the conditional district question usable without JavaScript too.
const districtSelect = document.querySelector('#id_district');
const otherDistrictPanel = document.querySelector('[data-district-other]');
if (districtSelect && otherDistrictPanel) {
  const otherDistrictInput = otherDistrictPanel.querySelector('input');
  const updateDistrict = () => {
    const isOther = districtSelect.selectedOptions[0]?.textContent.trim().toLowerCase() === 'other';
    otherDistrictPanel.hidden = !isOther;
    if (otherDistrictInput) {
      otherDistrictInput.disabled = !isOther;
      otherDistrictInput.required = isOther;
    }
  };
  districtSelect.addEventListener('change', updateDistrict);
  updateDistrict();
}

const applicationErrors = document.querySelector('[data-application-errors]');
if (applicationErrors) {
  applicationErrors.focus();
  applicationErrors.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (!link) return;
    const target = document.getElementById(link.hash.slice(1));
    const input = target?.matches('input, select, textarea') ? target : target?.querySelector('input, select, textarea');
    if (input) {
      event.preventDefault();
      input.focus();
      input.scrollIntoView({ block: 'center' });
    }
  });
}
