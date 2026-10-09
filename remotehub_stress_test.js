import http from "k6/http";

export const options = {
    scenarios: {
        remotehub_load: {
            executor: "constant-arrival-rate",
            rate: 10,
            timeUnit: "1s",
            duration: "10s",
            preAllocatedVUs: 5,
            maxVUs: 10,
        },
    },
};

export default function () {
    http.get("https://smartai-shop.vercel.app/", {
        headers: {
            "X-RemoteHub-Test": "true"
        }
    });
}
