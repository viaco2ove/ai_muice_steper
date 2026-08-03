import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// 不使用 StrictMode: WS 等有副作用的连接在 StrictMode 双调用下会产生连接抖动
ReactDOM.createRoot(document.getElementById('root')!).render(<App />)