/* Local TinyMCE, authenticated uploads, and save-after-upload semantics. */
document.addEventListener('DOMContentLoaded', () => {
  const fields = document.querySelectorAll('textarea.rich-editor');
  if (!fields.length || !window.tinymce) return;
  tinymce.init({
    selector: 'textarea.rich-editor', base_url: '/static/tinymce', suffix: '.min',
    license_key: 'gpl', height: 470, menubar: false, promotion: false, branding: false,
    plugins: 'link lists image table code autolink',
    toolbar: 'undo redo | blocks | bold italic | bullist numlist blockquote | link image table | removeformat code',
    block_formats: 'Paragraph=p; Heading 2=h2; Heading 3=h3; Heading 4=h4',
    content_css: '/static/css/editor.css',
    image_caption: true, image_description: true, image_dimensions: false,
    automatic_uploads: true, paste_data_images: true,
    file_picker_types: 'image', images_file_types: 'jpg,jpeg,png,webp',
    relative_urls: false, remove_script_host: true, convert_urls: true,
    images_upload_url: '/staff/images/upload/',
    images_upload_handler: async (blobInfo) => {
      const form = document.querySelector('.editor-form');
      const data = new FormData();
      data.append('file', blobInfo.blob(), blobInfo.filename());
      const response = await fetch('/staff/images/upload/', {
        method: 'POST', credentials: 'same-origin',
        headers: {'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value}, body: data
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || 'Image upload failed. Check your connection and staff sign-in, then try again.');
      }
      const result = await response.json();
      if (!result.location) throw new Error('The server did not return an image location.');
      return result.location;
    }
  });
  const form = document.querySelector('.editor-form');
  if (!form) return;
  let submitting = false;
  form.addEventListener('submit', async event => {
    if (submitting) return;
    event.preventDefault();
    const button = form.querySelector('button[type=submit]');
    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = 'Saving…';
    form.querySelector('.editor-error')?.remove();
    try {
      const editors = tinymce.get().filter(editor => form.contains(editor.getElement()));
      const results = await Promise.all(editors.map(editor => editor.uploadImages()));
      if (results.flat().some(result => !result.status)) throw new Error('An image could not be uploaded. Remove it or upload it again before saving.');
      tinymce.triggerSave();
      if (editors.some(editor => /src=["'](?:blob:|data:)/i.test(editor.getContent()))) {
        throw new Error('Wait for all images to finish uploading before saving.');
      }
      submitting = true;
      button.disabled = false;
      form.requestSubmit(button);
    } catch (error) {
      const alert = document.createElement('p');
      alert.className = 'editor-error';
      alert.setAttribute('role', 'alert');
      alert.textContent = error.message || 'Unable to save. Please try again.';
      form.prepend(alert);
      alert.scrollIntoView({block: 'center'});
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  });
});
