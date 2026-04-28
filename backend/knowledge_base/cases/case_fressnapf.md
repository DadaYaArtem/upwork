---
industry:
  - ecommerce
  - iot
  - fintech
tech_stack:
  - Backend (langchain/langgraph
  - AgenticAI):
  - - building AI agents
  - - further development of existing functionalities
  - - implementation of the newly defined architecture
client_type: company
region: Europe
---

# Fressnapf

## Общая информация
- Клиент: Fressnapf
- Локация: Germany
- Отрасль: e-commerce/IoT/Fintech
- Формат: Outstaff

## Команда
- Размер: 1 человек
- Состав: 1  Backend Developer with langchain/langgraph

## Стек
- Backend (langchain/langgraph
- AgenticAI):
- - building AI agents
- - further development of existing functionalities
- - implementation of the newly defined architecture

## Проблема клиента
Цель проекта:   - Поддержка и развитие e-commerce платформы (онлайн-магазин): улучшение каталога товаров, корзины, оформления заказов, механизмов складской логистики.  - Интеграция с новыми сервисами: онлайн-ветеринарь, страховки, IoT-устройства.  - Оптимизация бэкэнд-части для повышения масштабируемости, особенно в контексте роста заказов и логистики.  - Улучшение клиентского опыта: ускорение API, персонализация, рекомендации, работа с программой лояльности (“Fressnapf Friends”, возможно)  - Поддержка новых рынков (международная экспансия) на уровне backend: локализация, разные валюты, налоги, интеграция с локальными складами.  - Обеспечение надежности, безопасности, отказоустойчивости сервиса.

## Решение
Что мы делаем:   Разработка e-commerce микросервисов:  - API для каталога товаров: CRUD (создание/изменение/удаление) товаров, категорий, атрибутов (тип животного, корм, игрушки и пр.).  - Модули корзины и заказов: управление корзиной, расчёт стоимости, оформление заказов, интеграция с платежными системами.  - Управление пользователями: регистрация, аутентификация, профили, адреса доставки, история заказов.  - Лояльность и программы клиентов: интеграция с системой лояльности (“Fressnapf Friends”), расчёт бонусов, скидок, купонов.  Интеграция с логистикой и складом:   - API для связи с WMS (Warehouse Management System): получение статусов запасов, резервирование товаров, обновление складских остатков.  - Модули доставки: интеграция с службами доставки, расчёт сроков, стоимости, генерация лейблов.  - Обработка возвратов: логика возвращения товаров, возврат денег, повторная инвентаризация.  Сервисы цифровых услуг:   - Онлайн-врач: backend для “Online-Tierarzt”: прием записей, чат или видео, хранение медицинских данных животных, истории посещений.  - Страхование питомцев: API для работы с полисами, расчёта стоимости страховки, заявок на страхование, урегулирования.  - IoT-интеграция: обработка данных от трекеров питомцев (GPS), подключение устройств, хранение телеметрии, события (например, активности питомца).  Интернационализация:  - Поддержка нескольких локалей: язык, валюты, налоговые расчёты.  - Многоскладовая архитектура: выбирать ближайший склад для доставки, управлять запасами в разных странах.  - Регулировки под локальное законодательство (например, требования к ветеринарным лекарствам, отслеживание заказов).  Производительность и масштабируемость:  - Оптимизация API: кеширование, rate limiting, пагинация.  - Распределённая архитектура: микросервисы, возможное использование очередей (message queue) для асинхронных задач (наложение, логирование, уведомления).  - Мониторинг, логирование и alert-системы: чтобы отслеживать ошибки, производительность, SLA.  Безопасность и соответствие:   - Аутентификация и авторизация: безопасная регистрация, OAuth / JWT, роли (клиент, админ, локальный менеджер склада и пр.).  - Безопасность платежей: PCI-compliance, работа с платёжными провайдерами.  - Защита данных: шифрование личных и медицинских данных питомцев, GDPR (если действует в Европе).  DevOps & CI/CD:  - Настройка CI/CD пайплайнов для автоматического развёртывания backend-сервисов.  - Контейнеризация (Docker / Kubernetes) для масштабируемости и гибкости.  - Автоматическое тестирование: юнит-тесты, интеграционные тесты API.  Сотрудничество с фронтендом и продуктовой командой:   - Определение API контрактов с фронтом: что клиент видит, какие эндпоинты нужны.  - Работа над фичами совместно с продакт-менеджерами: новые сервисы, улучшения опыта.

Задачи команды: Что мы делаем:   Разработка e-commerce микросервисов:  - API для каталога товаров: CRUD (создание/изменение/удаление) товаров, категорий, атрибутов (тип животного, корм, игрушки и пр.).  - Модули корзины и заказов: управление корзиной, расчёт стоимости, оформление заказов, интеграция с платежными системами.  - Управление пользователями: регистрация, аутентификация, профили, адреса доставки, история заказов.  - Лояльность и программы клиентов: интеграция с системой лояльности (“Fressnapf Friends”), расчёт бонусов, скидок, купонов.  Интеграция с логистикой и складом:   - API для связи с WMS (Warehouse Management System): получение статусов запасов, резервирование товаров, обновление складских остатков.  - Модули доставки: интеграция с службами доставки, расчёт сроков, стоимости, генерация лейблов.  - Обработка возвратов: логика возвращения товаров, возврат денег, повторная инвентаризация.  Сервисы цифровых услуг:   - Онлайн-врач: backend для “Online-Tierarzt”: прием записей, чат или видео, хранение медицинских данных животных, истории посещений.  - Страхование питомцев: API для работы с полисами, расчёта стоимости страховки, заявок на страхование, урегулирования.  - IoT-интеграция: обработка данных от трекеров питомцев (GPS), подключение устройств, хранение телеметрии, события (например, активности питомца).  Интернационализация:  - Поддержка нескольких локалей: язык, валюты, налоговые расчёты.  - Многоскладовая архитектура: выбирать ближайший склад для доставки, управлять запасами в разных странах.  - Регулировки под локальное законодательство (например, требования к ветеринарным лекарствам, отслеживание заказов).  Производительность и масштабируемость:  - Оптимизация API: кеширование, rate limiting, пагинация.  - Распределённая архитектура: микросервисы, возможное использование очередей (message queue) для асинхронных задач (наложение, логирование, уведомления).  - Мониторинг, логирование и alert-системы: чтобы отслеживать ошибки, производительность, SLA.  Безопасность и соответствие:   - Аутентификация и авторизация: безопасная регистрация, OAuth / JWT, роли (клиент, админ, локальный менеджер склада и пр.).  - Безопасность платежей: PCI-compliance, работа с платёжными провайдерами.  - Защита данных: шифрование личных и медицинских данных питомцев, GDPR (если действует в Европе).  DevOps & CI/CD:  - Настройка CI/CD пайплайнов для автоматического развёртывания backend-сервисов.  - Контейнеризация (Docker / Kubernetes) для масштабируемости и гибкости.  - Автоматическое тестирование: юнит-тесты, интеграционные тесты API.  Сотрудничество с фронтендом и продуктовой командой:   - Определение API контрактов с фронтом: что клиент видит, какие эндпоинты нужны.  - Работа над фичами совместно с продакт-менеджерами: новые сервисы, улучшения опыта.

## Ключевые фичи
- Крупная европейская сеть зоомагазинов
- специализируется на кормах
- товарах для питомцев.
- У них сильное присутствие офлайн (физические магазины) + онлайн-магазин (омниканальный ритейлер).
- Они активно инвестируют в логистику: строят большой e-commerce склад (72 000 м²)
- чтобы ускорить доставку онлайн-заказов.
- Также у них партнёрство в IoT: Fressnapf сотрудничает с IoT-компаниями
- чтобы связывать владельцев питомцев и их животных через устройства (трекеры и др.) https://iot-venture.com/en/presse/iot-venture-forms-partnership-with-fressnapf-group-second-business-field-launched/?utm_source=chatgpt.com
- Еще они запустили онлайн-магазин ветеринарных лекарств совместно с аптечной группой


## О компании клиента (web research)
Fressnapf was founded in **1990** by **Torsten Toeller** in Erkelenz, Germany, with the first store opening in January 1990 ([en.wikipedia.org]).

 The company’s mission includes “We do everything we can to make the coexistence of people and animals easier, better and happier” ([reveliolabs.com]).

 - As of December 31, 2024, Fressnapf Holding SE employed **12,287** people and generated **€2.95 billion** in revenue ([de.wikipedia.org]). 
 - In Q2 2025, LTM (last twelve months) revenue reached **€3.6 billion**, with **8% growth** in adjusted EBITDA ([presse.fressnapf.de]). 
 - Workforce intelligence data from September 2025 reports **1,141 employees**, showing a 13.3% year‑on‑year decline—suggesting divergence in reporting criteria (perhaps excluding franchisees versus full group headcount) ([reveliolabs.com]).

 - In **July 2024**, British private equity firm **Cinven** acquired a **minority stake** in Fressnapf Holding SE, while Fressnapf took full ownership of Italian pet retailer Arcaplanet ([de.wikipedia.org]). 
 - On **December 5, 2024**, Fressnapf finalized the **acquisition of Arcaplanet**, adding around **560 stores** and over **€700 million in sales**, further strengthening its European market position ([presse.fressnapf.de]).

 - **Matt Simister**, former Tesco executive, was appointed **CEO** (interim) of Fressnapf | Maxi Zoo in **May 2025** ([fr.wikipedia.org]). 
 - Other executives include **Sebastian van Stiphout** (Managing Director) and **Torsten Toeller** as Chairman of the Supervisory Board ([de.wikipedia.org]).

---

Beyond core pet nutrition and accessories, Fressnapf operates exclusive private-label brands, particularly Real Nature, Select Gold, and Premiere, produced via their subsidiary **MultiFit Tiernahrungs GmbH** ([reddit.com]).

 - In **2025**, Fressnapf introduced the **Urban Store** concept in **Paris and Copenhagen**—compact (~100–200 m²) formats with curated assortments, digital integrations (Click & Collect, digital shelf extensions), and delivery via Wolt ([pet-worldwide.com]). 
 - The **Click & Collect** service, launched in select countries, accounted for **7% of e-commerce sales** in 2024 ([presse.fressnapf.de]). In 2025, Click & Collect continued to expand as part of omnichannel strategy ([presse.fressnapf.de]).

 Fressnapf serves both urban and suburban pet owners across Europe—family pet owners demanding omnichannel convenience, with loyalty driven by the strong loyalty program (64% of revenue from loyalty members in 2024) ([presse.fressnapf.de]).

 Operates both mainstream and competitive pricing across channels. Loyalty programs (e.g., Payback historically) and exclusive labels likely support value-driven pricing, but no explicit pricing tiers found.

 - **Grey Germany** was appointed as **marketing agency** in **January 2025**, to drive omnichannel brand growth; campaigns began showing results from May 2025 ([globalpetindustry.com]). 
 - **GK Software**: Fressnapf migrated over **2,750 stores** to the cloud-based **GK CLOUD4RETAIL** platform in **2025**, modernizing store processes (PoS, merchandising, digital interaction) ([euroshop.de]). 
 - **Kormotech** (Ukraine): In **January 2026**, Fressnapf began distributing Kormotech’s brands (Optimeal, Club 4 Paws, Delickcious) across **30 Fressnapf stores and 11 Hornbach outlets** in Romania and 15 other countries ([feedbusinessmea.com]). 
 - **Innovation Award 2025**: UK start-up **Inventor Smart Care**, creator of the Dental Wand (cat-friendly toothbrush), won Fressnapf’s **Innovation Award 2025**, earning shelf placement across Denmark, Switzerland, Austria, plus listing on German Fressnapf Marketplace ([allpawsindustry.com]).

---

Fressnapf has adopted **GK CLOUD4RETAIL**, a cloud-native retail platform for store services including PoS and omnichannel management ([euroshop.de]).

 No publicly available data on team size separately; workforce headcount available but not role-specific—**[Not found in public sources]**.

---

- **December 5, 2024**: Closed acquisition of Arcaplanet; Cinven acquired minority stake ([presse.fressnapf.de]).

 - **January 2025**: Grey Germany appointed as marketing agency ([globalpetindustry.com]). 
 - **August–September 2025**: Signed and executed migration to GK CLOUD4RETAIL platform ([euroshop.de]). 
 - **January 2026**: Partnered with Kormotech for distribution in Romania & beyond ([feedbusinessmea.com]).

 - **2025**: Pilot and rollout of **Urban Stores** in Paris and Copenhagen ([pet-worldwide.com]). 
 - **2024–2025**: Expansion of **Click & Collect** and loyalty integration ([presse.fressnapf.de]).

 - **2025 Innovation Award**: Inventor Smart Care awarded and featured on shelves and marketplace ([allpawsindustry.com]).

 - **May 2025**: Matt Simister named CEO ([fr.wikipedia.org]).

 - **Mid‑2025**: 76 new store openings in first half, including 35 in Q2, across France, Italy, Poland ([presse.fressnapf.de]). 
 - **Urban format expansion** ([pet-worldwide.com]).

---

## Значимость
- Проект в сфере e-commerce/IoT/Fintech
- Модель работы: Outstaff

## Ссылки
- https://www.fressnapf.de/