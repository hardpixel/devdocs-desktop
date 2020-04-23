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

  run(method, args) {
    this[method].call(this, ...args)
  }

  onElement(ref, callback) {
    const element = this.ref(ref)

    if (element) {
      return callback.call(this, element)
    }
  }

  postMessage(value, callback) {
    webkit.messageHandlers.desktop.postMessage({
      value: value,
      callback: callback
    })
  }

  isVisible(ref, callback) {
    this.onElement(ref, (element) => {
      const style = getComputedStyle(element)
      const value = style.display !== 'none'

      this.postMessage(value, callback)
    })
  }

  getValue(ref, callback) {
    this.onElement(ref, (element) => {
      const value = element.value || element.innerText
      this.postMessage(value, callback)
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
