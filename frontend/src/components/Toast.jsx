import { useEffect, useState } from 'react'

export default function Toast({ message, type = 'info' }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (message) {
      setVisible(true)
    } else {
      setVisible(false)
    }
  }, [message])

  if (!message) return null

  return (
    <div className={`toast ${visible ? 'show' : ''} ${type}`}>
      {message}
    </div>
  )
}
