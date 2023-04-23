// import { useState } from 'react'
// import * as bootstrap from "bootstrap"

function Breadcrumb ({ }) {
    return (
        <nav aria-label="breadcrumb">
            <ol className="breadcrumb">
                <li className="breadcrumb-item"><a href="#">Home</a></li>
                <li className="breadcrumb-item active" aria-current="page">Library</li>
            </ol>
        </nav>
    );
}

function Job ({ }) {
    return (
        <td>
            <strong>Job ID</strong><br />
            <small>peterbirch - 18:14 22/04/23</small>
        </td>
    );
}

function Message ({ }) {
    return (
        <tr>
            <td>TIME</td>
            <td>SEVERITY</td>
            <td>TEXT</td>
        </tr>
    );
}

export default function App() {
    // const [count, setCount] = useState(0)

    return (
        <>
            <header className="navbar navbar-dark bg-dark sticky-top shadow">
                <div className="container-fluid">
                    <a className="navbar-brand" href="#">
                        <img src="./assets/mascot_white.svg"
                            height="24"
                            className="d-inline-block align-text-top"
                            style={{ marginRight: "5px" }} />
                        Gator Hub
                    </a>
                    <div className="flex-fill"></div>
                    <div className="navbar-text"><Breadcrumb /></div>
                </div>
            </header>
            <div className="container-fluid">
                <div className="row">
                    <nav className="col-2 bg-light sidebar">
                        <table className="table table-sm">
                            <tbody>
                                <tr>
                                    <Job />
                                </tr>
                            </tbody>
                        </table>
                    </nav>
                    <main className="col-10" style={{ marginLeft: "auto" }}>
                        <table className="table table-striped table-sm">
                            <thead>
                                <tr>
                                    <th className="col-1">Time</th>
                                    <th className="col-1">Severity</th>
                                    <th className="col-10">Message</th>
                                </tr>
                            </thead>
                            <tbody>
                                <Message />
                            </tbody>
                        </table>
                    </main>
                </div>
            </div>
        </>
    )
}
