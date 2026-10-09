
import http from "k6/http";
import { sleep } from "k6";

export const options = {
    vus: 5,
    duration: "30s",
};

export default function () {
    http.get("https://smartai-shop.vercel.app/", {
        headers: {
            "X-RemoteHub-Test": "true"
        }
    });

    sleep(1);
}
