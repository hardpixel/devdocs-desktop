class DevDocsDesktop {
  constructor(refs) {
    this.refs = refs
  }

  query(selector) {
    return document.querySelector(selector)
  }

  ref(name) {
    if (name == 'document') {
      return document
    } else {
      return this.query(this.refs[name])
    }
  }

  onElement(ref, callback) {
    const element = this.ref(ref)

    if (element) {
      return callback.call(this, element)
    }
  }

  postMessage(value) {
    webkit.messageHandlers.desktop.postMessage({
      value: value
    })
  }

  isVisible(ref) {
    return this.onElement(ref, (element) => {
      const style = getComputedStyle(element)
      return style.display !== 'none'
    })
  }

  getValue(ref) {
    return this.onElement(ref, (element) => {
      return element.value || element.innerText
    })
  }

  setValue(ref, value) {
    this.onElement(ref, (element) => {
      element.value = value
    })
  }

  dispatchEvent(ref, type) {
    this.onElement(ref, (element) => {
      const event = new CustomEvent(type)
      element.dispatchEvent(event)
    })
  }

  sendKey(ref, type, code) {
    this.onElement(ref, (element) => {
      const event = new KeyboardEvent(type, { which: code })
      element.dispatchEvent(event)
    })
  }

  click(ref) {
    this.onElement(ref, (element) => {
      element.click()
    })
  }

  search(text) {
    this.setValue('searchInput', text)
    this.dispatchEvent('search', 'input')
  }

  navigate(appUrl, url) {
    const absPath = url.replace(appUrl, '')
    const element = this.query(`a[href="/${absPath}"]`)

    element && element.click()
  }
}

window.desktop = new DevDocsDesktop({
  search:      '._search',
  searchTag:   '._search-tag',
  searchInput: '._search-input',
  saveButton:  '._settings-btn-save'
})
