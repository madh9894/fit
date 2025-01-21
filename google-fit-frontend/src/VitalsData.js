import React, { useEffect, useState } from "react";

function VitalsData() {
    const [vitals, setVitals] = useState({});
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchVitals = async () => {
            try {
                const response = await fetch("http://127.0.0.1:5000/api/fit_vitals"); // Ensure the endpoint matches your backend.
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                setVitals(data);
            } catch (err) {
                setError(err.message);
            }
        };

        fetchVitals();
    }, []);

    if (error) {
        return <div>Error: {error}</div>;
    }

    const renderVitalData = (type, data) => {
        const dateTimeOptions = {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
        };

        if (!data || !Array.isArray(data)) {
            return <div>No data available for {type.toUpperCase()}.</div>;
        }

        return (
            <div>
                <h3>{type.replace("_", " ").toUpperCase()}</h3>
                <ul>
                    {data.map((entry, index) => (
                        <li key={index}>
                            <strong>Start Time:</strong>{" "}
                            {new Date(entry.start_time).toLocaleString(undefined, dateTimeOptions)}{" "}
                            <strong>End Time:</strong>{" "}
                            {new Date(entry.end_time).toLocaleString(undefined, dateTimeOptions)}{" "}
                            <strong>Value:</strong> {entry.value}
                        </li>
                    ))}
                </ul>
            </div>
        );
    };

    return (
        <div>
            <h1>Vitals Data</h1>
            {Object.keys(vitals).length > 0 ? (
                Object.entries(vitals).map(([type, data]) => (
                    <div key={type}>{renderVitalData(type, data)}</div>
                ))
            ) : (
                <p>Loading data...</p>
            )}
        </div>
    );
}

export default VitalsData;
